# [Choice of base image: Standard Devcontainers Python 3.11 image]
FROM mcr.microsoft.com/devcontainers/python:3.11

# Install core system dependencies required by browser engines (Playwright/Chromium)
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
       libnss3 \
       libasound2 \
       libatk-bridge2.0-0 \
       libgtk-3-0 \
       libx11-xcb1 \
       libxcb-dri3-0 \
       libxcomposite1 \
       libxcursor1 \
       libxdamage1 \
       libxext6 \
       libxfixes3 \
       libxi6 \
       libxrandr2 \
       libxrender1 \
       libxtst6 \
       libpangocairo-1.0-0 \
       libpango-1.0-0 \
       libharfbuzz0b \
       libatk1.0-0 \
       libcairo2 \
       libcups2 \
       libdbus-1-3 \
       libexpat1 \
       libfontconfig1 \
       libgbm1 \
       libgcc1 \
       libgconf-2-4 \
       libgdk-pixbuf2.0-0 \
       libglib2.0-0 \
       libnspr4 \
       libstdc++6 \
       libx11-6 \
       libxcb1 \
       libxshmfence1 \
       libxslt1.1 \
       libxxf86vm1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
