package estimate

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

const example = `{"instances":1,"hours_per_month":720,"hourly_rate":0.1,"storage_gb":100,"storage_rate":0.1,"egress_gb":50,"egress_rate":0.1}`

func mustParse(t *testing.T, body string) *Input {
	t.Helper()
	input, err := Parse(strings.NewReader(body))
	if err != nil {
		t.Fatalf("Parse() returned an unexpected error: %v", err)
	}
	return input
}

func TestKnownCalculation(t *testing.T) {
	result := Calculate(mustParse(t, example))
	if result.Compute != 7200 || result.Storage != 1000 || result.Egress != 500 || result.Total != 8700 || result.Currency != "USD" {
		t.Fatalf("unexpected result in cents: %+v", result)
	}
	body, err := json.Marshal(result)
	if err != nil {
		t.Fatal(err)
	}
	const expected = `{"compute":72.00,"storage":10.00,"egress":5.00,"total":87.00,"currency":"USD"}`
	if string(body) != expected {
		t.Fatalf("JSON = %s, want %s", body, expected)
	}
}

func TestStrictObjectBoundaries(t *testing.T) {
	cases := map[string]string{
		"empty":             "",
		"array":             "[]",
		"root null":         "null",
		"missing field":     strings.Replace(example, `"instances":1,`, "", 1),
		"null":              strings.Replace(example, `"storage_gb":100`, `"storage_gb":null`, 1),
		"quoted number":     strings.Replace(example, `"storage_gb":100`, `"storage_gb":"100"`, 1),
		"boolean":           strings.Replace(example, `"storage_gb":100`, `"storage_gb":true`, 1),
		"nested value":      strings.Replace(example, `"storage_gb":100`, `"storage_gb":{"value":100}`, 1),
		"unknown field":     strings.TrimSuffix(example, "}") + `,"region":"example"}`,
		"duplicate field":   strings.TrimSuffix(example, "}") + `,"instances":2}`,
		"trailing object":   example + `{}`,
		"trailing scalar":   example + `0`,
		"trailing garbage":  example + `oops`,
		"truncated object":  strings.TrimSuffix(example, "}"),
		"trailing comma":    strings.TrimSuffix(example, "}") + ",}",
		"fractional count":  strings.Replace(example, `"instances":1`, `"instances":1.5`, 1),
		"decimal count":     strings.Replace(example, `"instances":1`, `"instances":1.0`, 1),
		"exponential count": strings.Replace(example, `"instances":1`, `"instances":1e0`, 1),
	}
	for name, body := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := Parse(strings.NewReader(body)); err == nil {
				t.Fatal("Parse() accepted an invalid request")
			}
		})
	}
}

func TestRequiredNumericFields(t *testing.T) {
	fields := []string{
		`"instances":1`,
		`"hours_per_month":720`,
		`"hourly_rate":0.1`,
		`"storage_gb":100`,
		`"storage_rate":0.1`,
		`"egress_gb":50`,
		`"egress_rate":0.1`,
	}
	for _, field := range fields {
		name, _, _ := strings.Cut(field, ":")
		t.Run(name+" missing", func(t *testing.T) {
			body := strings.Replace(example, field+",", "", 1)
			if body == example {
				body = strings.Replace(example, ","+field, "", 1)
			}
			if _, err := Parse(strings.NewReader(body)); err == nil {
				t.Fatal("Parse() accepted a missing required field")
			}
		})
		t.Run(name+" null", func(t *testing.T) {
			body := strings.Replace(example, field, name+":null", 1)
			if _, err := Parse(strings.NewReader(body)); err == nil {
				t.Fatal("Parse() accepted a null required field")
			}
		})
	}
}

func TestNumericBounds(t *testing.T) {
	cases := []struct {
		field    string
		original string
		tooLarge string
	}{
		{"instances", "1", "10001"},
		{"hours_per_month", "720", "744.00000000000000000001"},
		{"hourly_rate", "0.1", "1000.00000000000000000001"},
		{"storage_gb", "100", "1000000.00000000000000000001"},
		{"storage_rate", "0.1", "1000.00000000000000000001"},
		{"egress_gb", "50", "1000000.00000000000000000001"},
		{"egress_rate", "0.1", "1000.00000000000000000001"},
	}
	for _, test := range cases {
		for _, value := range []string{"-1", test.tooLarge} {
			t.Run(test.field+"="+value, func(t *testing.T) {
				body := strings.Replace(example, `"`+test.field+`":`+test.original, `"`+test.field+`":`+value, 1)
				if _, err := Parse(strings.NewReader(body)); err == nil {
					t.Fatal("Parse() accepted an out-of-bounds number")
				}
			})
		}
	}
}

func TestBodySizeIncludesTrailingWhitespace(t *testing.T) {
	atLimit := example + strings.Repeat(" ", MaxBodyBytes-len(example))
	mustParse(t, atLimit)
	for _, body := range []string{atLimit + " ", strings.Repeat(" ", MaxBodyBytes+1)} {
		if _, err := Parse(strings.NewReader(body)); !errors.Is(err, ErrTooLarge) {
			t.Fatalf("Parse() error = %v, want ErrTooLarge", err)
		}
	}
}

func TestScientificExponentIsBoundedBeforeCalculation(t *testing.T) {
	for _, value := range []string{"1e999999999", "1e-999999999", "0e999999999", "1e4097", "1e-4097", "1e-999999999999999999999999999999"} {
		t.Run(value, func(t *testing.T) {
			body := strings.Replace(example, `"hourly_rate":0.1`, `"hourly_rate":`+value, 1)
			if _, err := Parse(strings.NewReader(body)); err == nil || !strings.Contains(err.Error(), "expoente") {
				t.Fatalf("Parse() error = %v, want a bounded-exponent error", err)
			}
		})
	}
	body := strings.Replace(example, `"hourly_rate":0.1`, `"hourly_rate":1e-4096`, 1)
	if result := Calculate(mustParse(t, body)); result.Compute != 0 {
		t.Fatalf("tiny valid rate should round to zero cents, got %d", result.Compute)
	}
	body = strings.Replace(example, `"hourly_rate":0.1`, `"hourly_rate":-1e-4096`, 1)
	if _, err := Parse(strings.NewReader(body)); err == nil {
		t.Fatal("Parse() accepted a tiny negative rate")
	}
}

func TestExactDecimalRounding(t *testing.T) {
	cases := []struct {
		name  string
		hours string
		rate  string
		cents Money
	}{
		{"half cent up", "1", "1.005", 101},
		{"below half cent", "1", "1.0049999999999999999999999999", 100},
		{"above half cent", "1", "1.0050000000000000000000000001", 101},
		{"fractional product", "0.1", "0.05", 1},
		{"carry to whole dollar", "1", "9.995", 1000},
		{"scientific notation", "1e1", "5e-4", 1},
		{"zero", "0", "1000", 0},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			body := `{"instances":1,"hours_per_month":` + test.hours + `,"hourly_rate":` + test.rate + `,"storage_gb":0,"storage_rate":0,"egress_gb":0,"egress_rate":0}`
			result := Calculate(mustParse(t, body))
			if result.Compute != test.cents || result.Total != test.cents {
				t.Fatalf("computed %d cents and total %d, want %d", result.Compute, result.Total, test.cents)
			}
		})
	}
}

func TestTotalSumsRoundedCategories(t *testing.T) {
	body := `{"instances":1,"hours_per_month":1,"hourly_rate":0.005,"storage_gb":1,"storage_rate":0.005,"egress_gb":1,"egress_rate":0.005}`
	result := Calculate(mustParse(t, body))
	if result.Compute != 1 || result.Storage != 1 || result.Egress != 1 || result.Total != 3 {
		t.Fatalf("each half-cent category should become one cent: %+v", result)
	}
}

func TestMaximumScenarioDoesNotOverflow(t *testing.T) {
	body := `{"instances":10000,"hours_per_month":744,"hourly_rate":1000,"storage_gb":1000000,"storage_rate":1000,"egress_gb":1000000,"egress_rate":1000}`
	result := Calculate(mustParse(t, body))
	if result.Compute != 744000000000 || result.Storage != 100000000000 || result.Egress != 100000000000 || result.Total != 944000000000 {
		t.Fatalf("unexpected maximum result in cents: %+v", result)
	}
	encoded, err := json.Marshal(result.Total)
	if err != nil || string(encoded) != "9440000000.00" {
		t.Fatalf("maximum amount JSON = %s, error = %v", encoded, err)
	}
}
