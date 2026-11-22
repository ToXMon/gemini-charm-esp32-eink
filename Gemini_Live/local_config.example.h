#pragma once
// Copy to ignored local_config.h and set your agent adapter HTTPS URL.
// Hermes or any other agent can be used via the API described in docs/AGENT_BACKEND.md.
#define HERMES_BASE_URL "https://agent.example.com"

// Public HTTPS/WSS bridge hostname and port. Certificate must chain to hermes_roots.h.
#define BRIDGE_HOST "bridge.example.com"
#define BRIDGE_PORT 443
