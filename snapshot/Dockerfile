FROM node:20-bookworm-slim
ARG CLAUDE_VERSION=2.1.94

ENV DEBIAN_FRONTEND=noninteractive
ENV DISABLE_AUTOUPDATER=1

RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip jq unzip pandoc \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash daytona

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}

RUN mkdir -p /etc/claude-code
COPY managed-settings.json /etc/claude-code/managed-settings.json

RUN mkdir -p /home/daytona/.claude
COPY claude-settings.json /home/daytona/.claude/settings.json

RUN mkdir -p /home/daytona/skills \
             /home/daytona/output \
             /home/daytona/workspace \
             /home/daytona/.claude/projects

RUN pip3 install pandas matplotlib requests openpyxl python-docx --break-system-packages

COPY CLAUDE.md /home/daytona/CLAUDE.md

RUN chown -R daytona:daytona /home/daytona

USER daytona
WORKDIR /home/daytona
