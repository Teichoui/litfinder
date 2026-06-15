# 📚 LitFinder: Book Search & Request Tool

<img src="src/frontend/public/logo.png" alt="LitFinder" width="200">

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/nemisishubris)

> [!IMPORTANT]
> This is an **actively maintained community fork** of [calibrain/shelfmark](https://github.com/calibrain/shelfmark). New features, bug fixes, and improvements are added here. The upstream project is no longer under active maintenance.

> [!NOTE]
> **This fork adds:**
> - **Kavita & Audiobookshelf integration** — live inventory sync so search results show "already owned" badges for books and series you already have in your library
> - **In-app file manager** — browse, rename, move, and create folders within any configured library folder directly from the UI (Files button in header)
> - **Library Folders registry** — a universal folder list under Settings → Library Folders, shared by the file manager; works with any library server
> - **Custom source plugin system** — install third-party source plugins into your config directory without modifying the container; plugins are auto-installed on startup ([LitFinder-Custom-Sources](https://github.com/NemesisHubris/LitFinder-Custom-Sources))
> - **"Leave in Place" output handler** — a noop delivery mode that skips moving the file after download, leaving it wherever the download client put it
> - **Multi-book flat-folder grouping** — when a download lands as a flat folder of files from multiple books, automatically splits them into per-book subfolders before delivery
> - **Richer title search** — multi-variant query generation strips edition markers, volume labels, and bracket annotations so the same book matches even when sources index it differently
> - **Language auto-detection** — detects book language from Anna's Archive distant-mirror paths so results are tagged correctly without a manual language field
> - **Activity feed display names** — admin users see real display names in the activity feed instead of raw user IDs
> - **Fuzzy title/author/ISBN matching** — shared utility for matching books across integrations using normalised, accent-folded comparisons
> - **Bug fixes** — AA slow-download infinite loop cap, empty destination dir cleanup on write-probe failure, activity snapshot refresh after cancel, rTorrent audiobook label, mirror URL query param handling, notification proxy passthrough, Transmission 100% complete detection
> - **Upstream ports** — IRC anti-spam cooldown + bot requirement, `?content_type=combined` URL param + `FORCE_COMBINED_SEARCH` setting, 7 security vulnerability fixes

LitFinder is a self-hosted web interface for searching and requesting books and audiobooks across multiple sources. Bring your own sources, metadata providers, and download clients to build a single hub for your digital library. Supports multiple users with a built-in request system, so you can share your instance with others and let them browse and request books on their own.

Works great alongside the following library tools, with support for automatic imports:
- [Calibre](https://calibre-ebook.com/)
- [Calibre-Web](https://github.com/janeczku/calibre-web)
- [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated)
- [Grimmory](https://github.com/grimmory-tools/grimmory)
- [Audiobookshelf](https://github.com/advplyr/audiobookshelf)

## ✨ Features

- **One-Stop Interface** - A clean, modern UI to search, browse, and download from multiple configured sources in one place
- **Multiple Sources** - Configurable web, torrent, usenet, and IRC source support
- **Audiobook Support** - Full audiobook search and download with dedicated processing
- **Flexible Search** - Search metadata providers (Hardcover, Open Library, Google Books) for rich book and audiobook discovery, or query configured sources directly
- **Multi-User & Requests** - Share your instance with others, let users browse and request books, and manage approvals with configurable notifications
- **Authentication** - Built-in login, OIDC single sign-on, proxy auth, and Calibre-Web database support
- **Real-Time Progress** - Unified download queue with live status updates across all sources
- **Network Flexibility** - Configurable proxy support, DNS settings, and optional Cloudflare handling for protected sources

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose

### Installation

1. Download the [docker-compose file](compose/docker-compose.yml):
   ```bash
   curl -O https://raw.githubusercontent.com/NemesisHubris/litfinder/main/compose/docker-compose.yml
   ```

2. Start the service:
   ```bash
   docker compose up -d
   ```

3. Open `http://localhost:8084`

Open the web interface, then configure the sources and settings you want to use.

### Volume Setup

```yaml
volumes:
  - /your/config/path:/config # Config, database, and artwork cache directory
  - /your/download/path:/books # Downloaded books
  - /client/path:/client/path # Optional: For Torrent/Usenet downloads, match your client directory exactly.
```

> **Tip**: Point the download volume to your CWA or Grimmory ingest folder for automatic import.

> **Note**: CIFS shares require `nobrl` mount option to avoid database lock errors.

### Non-root container mode

- Start the container as `1000:1000` with Docker `user: "1000:1000"` or `docker run --user 1000:1000`.
- For Kubernetes, set `runAsUser: 1000`, `runAsGroup: 1000`, and `runAsNonRoot: true` together.
- `PUID`/`PGID` keep the default root startup flow.
- Mounted paths must already be writable by `1000:1000`.
- `USING_TOR=true` requires root startup.

## ⚙️ Configuration

### Search Modes

**Direct**
- Queries configured sources directly

**Universal** (recommended)
- Search via metadata providers (Hardcover, Open Library, Google Books) for richer results
- Aggregates releases from multiple configured sources
- Full audiobook support

### Environment Variables

Environment variables work for initial setup and Docker deployments. They serve as defaults that can be overridden in the web interface.

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_PORT` | Web interface port | `8084` |
| `INGEST_DIR` | Book download directory | `/books` |
| `TZ` | Container timezone | `UTC` |
| `PUID` / `PGID` | Runtime user/group for the default root-startup flow (also supports legacy `UID`/`GID`) | `1000` / `1000` |
| `SEARCH_MODE` | `direct` or `universal` | `universal` |
| `USING_TOR` | Enable Tor routing (requires root startup) | `false` |

See the full [Environment Variables Reference](docs/environment-variables.md) for all available options.

Some of the additional options available in Settings:
- **Prowlarr** - Configure indexers and download clients to download books and audiobooks
- **Additional audiobook sources** - Configure additional sources for audiobook discovery
- **IRC** - Add details for IRC book sources and download directly from the UI
- **Library Link** - Add a link to your Calibre-Web or Grimmory instance in the UI header
- **File processing** - Customiseable download paths, file renaming and directory creation with template-based renaming
- **Network Settings** - Custom proxy support (SOCKS5 + HTTP/S) and configurable DNS
- **Format & Language** - Filter downloads by preferred formats, languages and sorting order
- **Metadata Providers** - Configure API keys for Hardcover, Open Library, etc.

## 🐳 Docker Variants

### Standard
```bash
docker compose up -d
```

The full-featured image with all network capabilities included.

#### Tor Routing
Optional Tor support for network privacy:
```bash
curl -O https://raw.githubusercontent.com/NemesisHubris/litfinder/main/compose/docker-compose.tor.yml
docker compose -f docker-compose.tor.yml up -d
```

**Notes:**
- Requires root startup
- Requires `NET_ADMIN` and `NET_RAW` capabilities
- Timezone is auto-detected from Tor exit node
- Custom DNS/proxy settings are ignored when Tor is active

### Lite
A lighter image without the built-in browser automation. Ideal for:

- **External services** - Already running FlareSolverr or similar for other applications
- **Alternative sources** - Using Prowlarr, IRC, or other configured sources
- **Audiobooks** - Using LitFinder primarily for audiobooks

```bash
curl -O https://raw.githubusercontent.com/NemesisHubris/litfinder/main/compose/docker-compose.lite.yml
docker compose -f docker-compose.lite.yml up -d
```

If you need browser-based access with the Lite image, configure an external resolver in Settings.

## 🔐 Authentication

Authentication is optional but recommended for shared or exposed instances. Multiple authentication methods are available in Settings:

**1. Single Username/Password**

**2. Proxy (Forward) Authentication**

Proxy auth trusts headers set by your reverse proxy (e.g. `X-Auth-User`). Ensure LitFinder is not directly exposed, and configure your proxy to strip/overwrite these headers for all inbound requests.

**3. OIDC (OpenID Connect)**

Integrate with your identity provider (Authelia, Authentik, Keycloak, etc.) for single sign-on. Supports PKCE flow, auto-discovery, group-based admin mapping, and auto-provisioning of new users.

**4. Calibre-Web Database**

If you're running Calibre-Web, you can reuse its user database by mounting it:

```yaml
volumes:
  - /path/to/calibre-web/app.db:/auth/app.db:ro
```

### Multi-User Support

With any authentication method enabled, LitFinder supports multi-user management with admin/user roles. Users can have per-user settings for download destinations, email recipients, and notification preferences. Non-admin users only see their own downloads and can submit book requests for admin review. Admins can configure request policies per source to control whether users can download directly, must submit a request, or are blocked entirely.

## Project Scope

LitFinder is a manual search and download tool — the entry point to your book library, not a library manager. It finds books, downloads them, and sends them to a configured destination.

**This fork extends that scope in a few targeted ways:**

- **Library awareness** — Kavita and Audiobookshelf inventory syncs surface "already owned" badges on search results, so you don't re-download what you already have. This is a read-only snapshot; LitFinder never writes to your library.
- **File manager** — a scoped, in-app browser for the folders you configure. Downloads still land via normal content-type routing; use the file manager afterward if you want to move something.

What the fork still does not do, and has no plans to do:

- **Manage your library** — it does not catalogue, tag, edit metadata, or restructure your collection
- **Monitor for new releases** — there is no watchlist, author alert, or "notify me when available" queue
- **Queue unavailable titles** — if a book isn't available now, LitFinder won't watch for it

## Contributing

LitFinder's core feature set is complete. Development focuses on stability, bug fixes, quality-of-life improvements, and refining the search experience. Contributions in these areas are welcome, please file issues or submit pull requests on GitHub.

Feature requests that fall outside the project scope (library integration, automation, collection management) will be closed. If you're unsure whether something fits, open a discussion first.

## Health Monitoring

The application exposes a health endpoint at `/api/health` (no authentication required). Add a health check to your compose:

```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:8084/api/health"]
  interval: 30s
  timeout: 30s
  retries: 3
```

## Logging

Logs are available via:
- `docker logs <container-name>`
- `/var/log/shelfmark/` inside the container (when `ENABLE_LOGGING=true`)

Log level is configurable via Settings or `LOG_LEVEL` environment variable.

## Development

```bash
# Quality checks
make checks              # Run ALL static analysis (frontend + Python)
make python-checks       # Run Ruff, BasedPyright, and Vulture
make install-python-dev  # Sync Python runtime + dev tools with uv

# Frontend development
make install     # Install dependencies
make dev         # Start Vite dev server (localhost:5173)
make build       # Production build
make frontend-typecheck  # TypeScript checks

# Backend (Docker)
make up          # Start backend via docker-compose.dev.yml
make down        # Stop services
make refresh     # Rebuild and restart
make restart     # Restart container
```

The frontend dev server proxies to the backend on port 8084.

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details. Original code by CaliBrain is MIT licensed; modifications and additions are licensed under AGPL-3.0.

## ⚠️ Disclaimer

LitFinder is a search interface that displays results from external metadata providers and sources. It does not host, store, or distribute any content. The developers are not responsible for how the tool is used or what is accessed through it.

Users are solely responsible for:
- Ensuring they have the legal right to download any material they access
- Complying with copyright laws and intellectual property rights in their jurisdiction
- Understanding and accepting the terms of any sources they configure

Use of this tool is entirely at your own risk.

## Support

Bug reports and questions → [open an issue](https://github.com/NemesisHubris/litfinder/issues) on GitHub.

If LitFinder saves you time, a coffee helps keep it going:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/nemisishubris)
