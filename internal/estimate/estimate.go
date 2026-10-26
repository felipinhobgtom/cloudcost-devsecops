// Package estimate validates illustrative prices and calculates monthly costs.
package estimate

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"strconv"
)

const MaxBodyBytes = 4096

var ErrTooLarge = errors.New("o corpo JSON deve ter no máximo 4096 bytes")

var (
	hundred = big.NewInt(100)
	one     = big.NewInt(1)
)

// Input can only be constructed with validated, bounded values through Parse.
// Its rational numbers must not be copied after initialization.
type Input struct {
	instances   int64
	hours       big.Rat
	hourlyRate  big.Rat
	storageGB   big.Rat
	storageRate big.Rat
	egressGB    big.Rat
	egressRate  big.Rat
}

// Money stores whole USD cents, not a floating-point approximation.
type Money int64

// MarshalJSON writes a dollar amount with exactly two fractional digits.
func (m Money) MarshalJSON() ([]byte, error) {
	const digits = "0123456789"
	cents := int64(m)
	whole, fraction := cents/100, cents%100
	out := make([]byte, 0, 24)
	if cents < 0 {
		out = append(out, '-')
		whole, fraction = -whole, -fraction
	}
	out = strconv.AppendInt(out, whole, 10)
	out = append(out, '.', digits[fraction/10], digits[fraction%10])
	return out, nil
}

type Result struct {
	Compute  Money  `json:"compute"`
	Storage  Money  `json:"storage"`
	Egress   Money  `json:"egress"`
	Total    Money  `json:"total"`
	Currency string `json:"currency"`
}

// Parse accepts one JSON object, without unknown or repeated keys. Reading is
// bounded before decoding, including when excess bytes are trailing whitespace.
func Parse(reader io.Reader) (*Input, error) {
	body, err := io.ReadAll(io.LimitReader(reader, MaxBodyBytes+1))
	if err != nil {
		return nil, errors.New("não foi possível ler o corpo da requisição")
	}
	if len(body) > MaxBodyBytes {
		return nil, ErrTooLarge
	}

	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.UseNumber()
	opening, err := decoder.Token()
	if err != nil || opening != json.Delim('{') {
		return nil, errors.New("envie um objeto JSON válido")
	}

	input := new(Input)
	var seen uint8
	for decoder.More() {
		keyToken, err := decoder.Token()
		if err != nil {
			return nil, errors.New("envie um objeto JSON válido")
		}
		key, ok := keyToken.(string)
		if !ok {
			return nil, errors.New("envie um objeto JSON válido")
		}

		var bit uint8
		var maximum int64
		var destination *big.Rat
		switch key {
		case "instances":
			bit, maximum = 1, 10000
		case "hours_per_month":
			bit, maximum, destination = 2, 744, &input.hours
		case "hourly_rate":
			bit, maximum, destination = 4, 1000, &input.hourlyRate
		case "storage_gb":
			bit, maximum, destination = 8, 1000000, &input.storageGB
		case "storage_rate":
			bit, maximum, destination = 16, 1000, &input.storageRate
		case "egress_gb":
			bit, maximum, destination = 32, 1000000, &input.egressGB
		case "egress_rate":
			bit, maximum, destination = 64, 1000, &input.egressRate
		default:
			return nil, errors.New("o JSON contém um campo desconhecido")
		}
		if seen&bit != 0 {
			return nil, fmt.Errorf("o campo %s foi repetido", key)
		}
		seen |= bit

		value, err := decoder.Token()
		if err != nil {
			return nil, errors.New("envie um objeto JSON válido")
		}
		number, ok := value.(json.Number)
		if !ok {
			return nil, fmt.Errorf("%s deve ser um número, sem aspas e não nulo", key)
		}
		if key == "instances" {
			count, err := strconv.ParseInt(string(number), 10, 64)
			if err != nil || count < 0 || count > maximum {
				return nil, errors.New("instances deve ser um inteiro entre 0 e 10000")
			}
			input.instances = count
			continue
		}
		if err := parseDecimal(number, maximum, destination); err != nil {
			return nil, fmt.Errorf("%s: %w", key, err)
		}
	}

	closing, err := decoder.Token()
	if err != nil || closing != json.Delim('}') {
		return nil, errors.New("envie um objeto JSON válido")
	}
	if seen != 127 {
		return nil, errors.New("todos os sete campos do cálculo são obrigatórios")
	}
	if _, err := decoder.Token(); err != io.EOF {
		return nil, errors.New("envie apenas um objeto JSON, sem conteúdo adicional")
	}
	return input, nil
}

func parseDecimal(number json.Number, maximum int64, destination *big.Rat) error {
	raw := string(number)
	// The body limit bounds digits but not an exponent's numeric value.
	// Bound that value before math/big can allocate a power of ten.
	for i := range raw {
		if raw[i] != 'e' && raw[i] != 'E' {
			continue
		}
		exponent := 0
		for j := i + 1; j < len(raw); j++ {
			if raw[j] == '+' || raw[j] == '-' {
				continue
			}
			exponent = exponent*10 + int(raw[j]-'0')
			if exponent > 4096 {
				return errors.New("use expoente científico entre -4096 e 4096")
			}
		}
		break
	}
	if _, ok := destination.SetString(raw); !ok {
		return errors.New("envie um número decimal válido")
	}
	var bound big.Rat
	bound.SetInt64(maximum)
	if destination.Sign() < 0 || destination.Cmp(&bound) > 0 {
		return fmt.Errorf("deve estar entre 0 e %d", maximum)
	}
	return nil
}

// Calculate rounds each category to cents, with exact half cents rounded up.
// The total is the sum of those rounded categories, matching the displayed bill.
func Calculate(input *Input) Result {
	var amount, instances big.Rat
	instances.SetInt64(input.instances)
	amount.Mul(&input.hours, &input.hourlyRate)
	amount.Mul(&amount, &instances)
	compute := roundCents(&amount)
	amount.Mul(&input.storageGB, &input.storageRate)
	storage := roundCents(&amount)
	amount.Mul(&input.egressGB, &input.egressRate)
	egress := roundCents(&amount)
	return Result{
		Compute:  compute,
		Storage:  storage,
		Egress:   egress,
		Total:    compute + storage + egress,
		Currency: "USD",
	}
}

func roundCents(amount *big.Rat) Money {
	var scaled, whole, remainder big.Int
	scaled.Mul(amount.Num(), hundred)
	whole.QuoRem(&scaled, amount.Denom(), &remainder)
	remainder.Lsh(&remainder, 1)
	if remainder.Cmp(amount.Denom()) >= 0 {
		whole.Add(&whole, one)
	}
	return Money(whole.Int64())
}
