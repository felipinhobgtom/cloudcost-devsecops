// Package web serves the embedded interface and the calculation API.
package web

import (
	_ "embed"
	"encoding/json"
	"errors"
	"mime"
	"net/http"
	"strconv"

	"cloudcost/internal/estimate"
)

//go:embed static/index.html
var indexHTML []byte

//go:embed static/styles.css
var stylesCSS []byte

//go:embed static/app.js
var appJS []byte

func NewHandler() http.Handler {
	return http.HandlerFunc(serveHTTP)
}

func serveHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Security-Policy", "default-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("X-Frame-Options", "DENY")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
	w.Header().Set("Cache-Control", "no-store")

	switch r.URL.Path {
	case "/":
		serveAsset(w, r, "text/html; charset=utf-8", indexHTML)
	case "/styles.css":
		serveAsset(w, r, "text/css; charset=utf-8", stylesCSS)
	case "/app.js":
		serveAsset(w, r, "text/javascript; charset=utf-8", appJS)
	case "/healthz":
		if r.Method != http.MethodGet {
			methodNotAllowed(w, http.MethodGet)
			return
		}
		writeJSON(w, http.StatusOK, struct {
			Status string `json:"status"`
		}{Status: "ok"})
	case "/api/estimate":
		serveEstimate(w, r)
	default:
		writeError(w, http.StatusNotFound, "recurso não encontrado")
	}
}

func serveAsset(w http.ResponseWriter, r *http.Request, contentType string, content []byte) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		methodNotAllowed(w, "GET, HEAD")
		return
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Length", strconv.Itoa(len(content)))
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = w.Write(content)
	}
}

func serveEstimate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w, http.MethodPost)
		return
	}
	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || mediaType != "application/json" {
		writeError(w, http.StatusUnsupportedMediaType, "use Content-Type: application/json")
		return
	}
	if r.ContentLength > estimate.MaxBodyBytes {
		writeError(w, http.StatusRequestEntityTooLarge, estimate.ErrTooLarge.Error())
		return
	}
	input, err := estimate.Parse(r.Body)
	if err != nil {
		status := http.StatusBadRequest
		if errors.Is(err, estimate.ErrTooLarge) {
			status = http.StatusRequestEntityTooLarge
		}
		writeError(w, status, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, estimate.Calculate(input))
}

func methodNotAllowed(w http.ResponseWriter, allowed string) {
	w.Header().Set("Allow", allowed)
	writeError(w, http.StatusMethodNotAllowed, "método HTTP não permitido")
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, struct {
		Error string `json:"error"`
	}{Error: message})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
