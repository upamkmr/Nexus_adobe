# AI Assistant Crawler Specifications & Ingestion Protocols

This reference guide documents the technical specifications, User-Agent tokens, IP verification mechanisms, and rendering capabilities for major AI retrieval crawlers (covering Round 2 Appendix A, B, and C).

---

## 1. Major AI Crawler User-Agent Tokens

When an AI assistant (such as ChatGPT, Claude, Perplexity, Copilot, or Gemini) searches the web in real-time to answer user questions, it uses specialized retrieval crawlers. Blocking these tokens in `robots.txt` makes a brand completely invisible to conversational AI.

| AI Assistant / Engine | Primary User-Agent Token | Operator | Primary Role | JavaScript Execution? |
|---|---|---|---|---|
| **ChatGPT Search / GPT** | `GPTBot` | OpenAI | Corpus indexing & search | **No** (Raw HTTP only) |
| **ChatGPT Browsing** | `ChatGPT-User` | OpenAI | Real-time user browsing | **Limited / No** |
| **Claude Search** | `ClaudeBot` | Anthropic | Training & search retrieval | **No** (Raw HTTP only) |
| **Perplexity AI** | `PerplexityBot` | Perplexity | Real-time answer retrieval | **Limited** (Fast HTTP first) |
| **Google AI Overviews / Gemini** | `Google-Extended` | Google | AI training / overviews control | Handled via Googlebot crawler |
| **Apple Intelligence** | `Applebot-Extended` | Apple | Siri & Apple Intelligence | **No** (Raw HTTP only) |
| **Cohere AI** | `cohere-ai` | Cohere | Enterprise RAG retrieval | **No** (Raw HTTP only) |
| **Common Crawl** | `CCBot` | Common Crawl | Foundation model training data | **No** (Raw HTTP only) |

---

## 2. The Raw-vs-Rendered Ingestion Trap (Appendix C)

A critical failure mode for modern websites is **relying on client-side JavaScript to assemble text**:

1. **Zero-JS Ingestion**: The overwhelming majority of AI retrieval crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`) perform lightweight, high-throughput HTTP GET requests. They do **not** spin up full Chromium/WebKit headless browser instances with 5-second hydration timers for every fetched URL due to infrastructure cost and latency constraints.
2. **The Blank DOM Shell**: If a website uses React, Angular, Vue, or Svelte in SPA (Single-Page Application) mode without Server-Side Rendering (SSR) or Static Site Generation (SSG), the server response contains only:
   ```html
   <div id="root"></div>
   <script src="/bundle.js"></script>
   ```
3. **Outcome**: The AI crawler extracts 0 bytes of semantic text, marks the page as empty or low quality, and cannot cite facts from it.

### Recommended Prerendering Configuration (Nginx)

For sites that cannot be migrated to full SSR (e.g. Next.js / Nuxt.js), configure reverse-proxy edge prerendering for AI bots:

```nginx
# Nginx bot prerender rule
map $http_user_agent $is_ai_bot {
    default 0;
    ~*(GPTBot|ChatGPT-User|ClaudeBot|PerplexityBot|Applebot-Extended|cohere-ai) 1;
}

server {
    listen 443 ssl;
    server_name example.com;

    location / {
        if ($is_ai_bot) {
            # Proxy request to a headless prerender service (e.g., Rendertron or Prerender.io)
            proxy_pass http://prerender-service:3000/render/$scheme://$host$request_uri;
            break;
        }
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 3. Optimal `robots.txt` AI Policy

To ensure complete AI discoverability while maintaining granular control over sensitive sections:

```robots
# ==========================================
# Robots.txt Policy for AI Discoverability
# ==========================================

# Explicitly permit AI retrieval crawlers on public documentation & product pages
User-agent: GPTBot
Allow: /
Disallow: /admin/
Disallow: /checkout/
Disallow: /api/private/

User-agent: ClaudeBot
Allow: /
Disallow: /admin/
Disallow: /checkout/

User-agent: PerplexityBot
Allow: /
Disallow: /admin/
Disallow: /checkout/

User-agent: Applebot-Extended
Allow: /

# Declare XML Sitemap for crawler discovery
Sitemap: https://example.com/sitemap.xml
```

---

## 4. Rate Limiting & Politeness Protocols

AI crawlers typically respect polite request intervals:
- Keep server latency under 500ms for HTTP 200 responses.
- Return proper HTTP 304 Not Modified when `If-Modified-Since` headers are supplied.
- Provide HTTP 429 Too Many Requests with a `Retry-After: 5` header if load spikes occur, rather than dropping TCP connections or returning 403 Forbidden.
