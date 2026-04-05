---
layout: default
title: API Reference
---

<style>
  /* override default layout padding so swagger gets full width */
  .swagger-wrap { margin: -48px -24px -80px; }
  #swagger-ui .topbar { display: none !important; }
  #swagger-ui { background: #0d1117; }
  #swagger-ui .swagger-ui { background: #0d1117; color: #e6edf3; }
  #swagger-ui .swagger-ui .info .title { color: #e6edf3; }
  #swagger-ui .swagger-ui .scheme-container { background: #161b22; box-shadow: none; border-bottom: 1px solid #21262d; padding: 16px 24px; }
  #swagger-ui .swagger-ui .opblock-tag { color: #e6edf3; border-bottom: 1px solid #21262d; }
  #swagger-ui .swagger-ui .opblock .opblock-summary-description { color: #8b949e; }
  #swagger-ui .swagger-ui section.models { background: #161b22; border: 1px solid #21262d; }
</style>

<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />

<div class="swagger-wrap">
  <div id="swagger-ui"></div>
</div>

<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: "{{ site.baseurl }}/openapi.yaml",
    dom_id: "#swagger-ui",
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: "BaseLayout",
    deepLinking: true,
    tryItOutEnabled: false,
  });
</script>
