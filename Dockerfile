FROM python:3.10-slim AS base
FROM base AS builder
# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
# Install AWS CLI v2
RUN curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
# RUN curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip" \
    && unzip -q awscliv2.zip \
    && ./aws/install -i /aws-cli -b /usr/local/bin \
    && rm -rf aws awscliv2.zip
COPY requirements.txt /requirements.txt
RUN pip install --user --no-warn-script-location -r /requirements.txt

FROM base
# Reinstall only runtime packages needed for AWS CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 libssl3 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
COPY --from=builder /aws-cli /aws-cli
ENV PATH="/root/.local/bin:/aws-cli/v2/current/bin:$PATH"
WORKDIR /app
COPY src/ /app/
CMD [ "python", "-u", "main.py"]
