FROM ubuntu:24.04

# Install base OS dependencies: Python stack for local vector embeddings, network tools, editors
RUN apt update && apt install -y \
python3 python3-pip python3-venv python3-dev python3-full \
curl ca-certificates git nano bash wget

# Install Node.js 18.x LTS runtime (required for official TypeScript OpenClaw & Claude/OpenAI gateways)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
&& apt install -y nodejs

# Install official OpenClaw core CLI globally via NPM
# Creates working binary /usr/local/bin/openclaw (no broken Python pip library)
RUN npm install -g openclaw

# Install ONLY valid published NPM gateway packages
# Removed notebook-lm (404 not found on npm registry, invalid package name)
RUN npm install -g @anthropic-ai/claude-code openai-agent

# Set container working directory to /app
WORKDIR /app

# Create isolated Python virtual environment ONLY for local Notebook LM embedding workloads
# This venv is separate from OpenClaw Node.js runtime, eliminates all cmdop import errors
RUN python3 -m venv /app/venv

# Configure root user shell environment:
# 1. Auto activate venv on shell login
# 2. Prioritize /usr/local/bin (npm global binaries) in PATH for openclaw CLI
RUN echo "source /app/venv/bin/activate" >> /root/.bashrc \
&& echo "export PATH=\"/usr/local/bin:\$PATH\"" >> /root/.bashrc

# Copy host startup script into container /app/init-skills.sh
# Host source: /home/anne/openclaw-full-stack/init-skills.sh
# Container destination: /app/init-skills.sh
COPY init-skills.sh ./
# Grant execute permission to entrypoint script
RUN chmod +x init-skills.sh

# Container entrypoint: auto-run skill installation, agent loop & gateways on startup
CMD ["/app/init-skills.sh"]
