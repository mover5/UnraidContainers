FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# ── System dependencies ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    jq \
    git \
    tmux \
    build-essential \
    openssh-client \
    openssh-server \
    bubblewrap \
    socat \
    openssl \
    sudo \
    locales \
    ca-certificates \
    gnupg \
    vim \
    nano \
    rsync \
    unzip \
    python3 \
    python3-pip \
    python3-venv \
    mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Set locale
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# ── Node.js 22 LTS ───────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── GitHub CLI ────────────────────────────────────────────────────────
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# ── Azure CLI ─────────────────────────────────────────────────────────
RUN curl -fsSL https://aka.ms/InstallAzureCLIDeb | bash \
    && rm -rf /var/lib/apt/lists/*

# ── .NET SDK 9 (STS) ──────────────────────────────────────────────────
# Install AFTER Azure CLI, which pulls in dotnet 8 via apt as a dependency.
# Remove the apt-installed dotnet, then install dotnet 9 and symlink over /usr/bin/dotnet.
RUN apt-get remove -y dotnet-sdk-8.0 dotnet-host-8.0 2>/dev/null; apt-get autoremove -y 2>/dev/null; \
    rm -f /usr/bin/dotnet && rm -rf /usr/lib/dotnet \
    && curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && chmod +x /tmp/dotnet-install.sh \
    && /tmp/dotnet-install.sh --channel 9.0 --install-dir /usr/share/dotnet \
    && rm /tmp/dotnet-install.sh \
    && ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet

# ── Playwright system dependencies ───────────────────────────────────
RUN npx playwright install-deps chromium

# ── Create claude user ────────────────────────────────────────────────
RUN userdel -r ubuntu 2>/dev/null; groupdel ubuntu 2>/dev/null; \
    groupadd -g 1000 claude \
    && useradd -m -u 1000 -g claude -s /bin/bash claude \
    && echo 'claude ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/claude \
    && mkdir -p /home/claude/.ssh \
    && mkdir -p /home/claude/.local/bin \
    && mkdir -p /home/claude/.claude \
    && mkdir -p /repos

# ── SSH server setup ─────────────────────────────────────────────────
RUN mkdir -p /run/sshd
COPY config/sshd_config /etc/ssh/sshd_config

# ── Default tmux config ──────────────────────────────────────────────
COPY config/tmux.conf /etc/tmux.conf

# Fix ownership before installing user-level tools
RUN chown -R claude:claude /home/claude /repos

# ── Install Claude Code (native installer, as claude user) ───────────
USER claude
WORKDIR /home/claude
RUN curl -fsSL https://claude.ai/install.sh | bash
USER root
# Copy to system path so it survives /home/claude volume mounts
RUN cp /home/claude/.local/bin/claude /usr/local/bin/claude

# ── Install Playwright browsers (as claude user) ─────────────────────
# Set user-writable browser path so installs don't require sudo
ENV PLAYWRIGHT_BROWSERS_PATH=/home/claude/.cache/ms-playwright
USER claude
RUN mkdir -p /home/claude/.cache/ms-playwright && npx playwright install chromium
USER root

# ── PATH for claude user ─────────────────────────────────────────────
# ENV sets PATH for Docker-started processes (entrypoint)
ENV PATH="/home/claude/.npm-global/bin:/home/claude/.local/bin:${PATH}"
# profile.d script sets PATH for SSH login shells (not affected by volume mounts)
RUN printf 'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"\nexport PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright"\n' > /etc/profile.d/claude-path.sh

# ── Entrypoint ────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/home/claude", "/repos"]

ENTRYPOINT ["/entrypoint.sh"]
