# power-grid-reference のNode-RED HMI向け共通image。
# platform-specific base digestに固定し、iproute2をbuild時に同梱する。
FROM nodered/node-red:3.1.0@sha256:bd1091b9c273cfe6bad85873cb311c794cfc0f209531897ec36b8c48be06c921

USER root
RUN apk add --no-cache iproute2 \
    && command -v ip \
    && command -v tc
USER node-red

CMD ["npm", "start", "--", "--userDir", "/data"]
