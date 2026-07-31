FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-server \
        sudo \
        curl \
        procps \
        iproute2 \
        iputils-ping \
        net-tools \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash ops \
    && echo "ops ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ops \
    && chmod 440 /etc/sudoers.d/ops

RUN mkdir -p /var/run/sshd \
    && ssh-keygen -A

COPY init-ssh.sh /init-ssh.sh
RUN sed -i 's/\r$//' /init-ssh.sh && chmod +x /init-ssh.sh

EXPOSE 22

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=10s \
    CMD pgrep sshd > /dev/null || exit 1

CMD ["/init-ssh.sh"]
