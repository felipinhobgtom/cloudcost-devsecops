FROM golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb AS builder

WORKDIR /src
ENV CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOPROXY=off \
    GOSUMDB=off \
    GOCACHE=/tmp/go-cache \
    GOMODCACHE=/tmp/go-mod
COPY --chown=65532:65532 . .
USER 65532:65532
RUN go build -trimpath -buildvcs=false -ldflags="-s -w -buildid=" -o /tmp/cloudcost ./cmd/server

FROM scratch
ARG VCS_REF=uncommitted
ARG SOURCE_DATE_EPOCH=0
LABEL org.opencontainers.image.title="CloudCost" \
      org.opencontainers.image.description="Estimador educacional de custos mensais de nuvem; preços fornecidos pelo usuário" \
      org.opencontainers.image.source="https://github.com/felipinhobgtom/cloudcost-devsecops" \
      org.opencontainers.image.revision="${VCS_REF}"
COPY --from=builder --chown=65532:65532 /tmp/cloudcost /cloudcost
USER 65532:65532
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 CMD ["/cloudcost", "healthcheck"]
ENTRYPOINT ["/cloudcost"]
