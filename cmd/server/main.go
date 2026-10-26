package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"cloudcost/internal/web"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	portText := os.Getenv("PORT")
	if portText == "" {
		portText = "8080"
	}
	port, err := strconv.ParseUint(portText, 10, 16)
	if err != nil || port == 0 {
		fmt.Fprintln(os.Stderr, "PORT deve ser um número entre 1 e 65535")
		return 2
	}
	if len(args) != 0 {
		if len(args) == 1 && args[0] == "healthcheck" {
			return healthcheck(port)
		}
		fmt.Fprintln(os.Stderr, "uso: cloudcost [healthcheck]")
		return 2
	}
	return serve(strconv.FormatUint(port, 10))
}

func serve(port string) int {
	logger := log.New(os.Stderr, "cloudcost: ", log.LstdFlags)
	server := &http.Server{
		Addr:              net.JoinHostPort("", port),
		Handler:           web.NewHandler(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    16 << 10,
		ErrorLog:          logger,
	}

	shutdownSignal, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	serveError := make(chan error, 1)
	go func() {
		serveError <- server.ListenAndServe()
	}()
	logger.Printf("servidor HTTP em :%s; produção exige HTTPS no proxy de entrada", port)

	select {
	case err := <-serveError:
		if !errors.Is(err, http.ErrServerClosed) {
			logger.Printf("não foi possível servir HTTP: %v", err)
			return 1
		}
	case <-shutdownSignal.Done():
		stop()
		shutdownContext, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownContext); err != nil {
			_ = server.Close()
			logger.Printf("encerramento excedeu o prazo: %v", err)
			return 1
		}
		if err := <-serveError; !errors.Is(err, http.ErrServerClosed) {
			logger.Printf("erro ao encerrar HTTP: %v", err)
			return 1
		}
		logger.Print("servidor encerrado")
	}
	return 0
}

func healthcheck(port uint64) int {
	// A direct loopback transport needs neither a shell nor CA certificates in
	// the scratch image, and cannot be redirected through an environment proxy.
	client := &http.Client{
		Timeout: 3 * time.Second,
		Transport: &http.Transport{
			Proxy:             nil,
			DisableKeepAlives: true,
			DialContext: (&net.Dialer{
				Timeout: 2 * time.Second,
			}).DialContext,
		},
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	target := url.URL{
		Scheme: "http",
		Host:   net.JoinHostPort("127.0.0.1", strconv.FormatUint(port, 10)),
		Path:   "/healthz",
	}
	response, err := client.Get(target.String())
	if err != nil {
		fmt.Fprintln(os.Stderr, "healthcheck: serviço indisponível")
		return 1
	}
	defer response.Body.Close()
	var payload struct {
		Status string `json:"status"`
	}
	if response.StatusCode != http.StatusOK || json.NewDecoder(io.LimitReader(response.Body, 256)).Decode(&payload) != nil || payload.Status != "ok" {
		fmt.Fprintln(os.Stderr, "healthcheck: resposta inválida")
		return 1
	}
	return 0
}
