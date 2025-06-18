#!/bin/bash
# Startup script for Minecraft server VM

# Update system
apt-get update

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create minecraft directory
mkdir -p /opt/minecraft
cd /opt/minecraft

# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
services:
  minecraft:
    image: itzg/minecraft-server:latest
    container_name: minecraft-server
    ports:
      - "25565:25565"
      - "25575:25575"
    environment:
      EULA: "TRUE"
      TYPE: "VANILLA"
      VERSION: "1.21.1"
      MEMORY: "2G"
      SPAWN_PROTECTION: 0
      MAX_PLAYERS: 10
      ENABLE_RCON: "true"
      RCON_PASSWORD: "minecraft"
      RCON_PORT: 25575
      ONLINE_MODE: "false"
      DIFFICULTY: "peaceful"
      GAMEMODE: "creative"
      SPAWN_MONSTERS: "false"
      SPAWN_ANIMALS: "true"
      VIEW_DISTANCE: 10
    volumes:
      - minecraft_data:/data
    restart: unless-stopped

volumes:
  minecraft_data:
EOF

# Start Minecraft server
docker-compose up -d

echo "Minecraft server startup complete!"
