---
layout: default
title: Home
---

<style>
  .hero {
    text-align: center;
    padding: 48px 0 56px;
    border-bottom: 1px solid #21262d;
    margin-bottom: 48px;
  }
  .hero-badge {
    display: inline-block;
    background: #238636;
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 20px;
  }
  .hero h1 {
    font-size: clamp(28px, 5vw, 44px);
    font-weight: 700;
    letter-spacing: -.02em;
    line-height: 1.15;
    margin-bottom: 14px;
    border: none !important;
    padding: 0 !important;
  }
  .hero h1 span { color: #58a6ff; }
  .hero-sub {
    font-size: 16px;
    color: #8b949e;
    max-width: 520px;
    margin: 0 auto 28px;
  }
  .hero-btns { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none !important;
    transition: opacity .15s;
  }
  .btn:hover { opacity: .75; }
  .btn-green { background: #238636; color: #fff !important; }
  .btn-dark { background: #21262d; color: #e6edf3 !important; border: 1px solid #30363d; }

  .section-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: #58a6ff;
    margin-bottom: 18px;
  }

  .tracks {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 14px;
    margin-bottom: 52px;
  }
  .card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 22px;
    text-decoration: none !important;
    color: inherit !important;
    transition: border-color .15s, transform .15s;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .card:hover { border-color: #58a6ff; transform: translateY(-2px); }
  .card-icon { font-size: 26px; line-height: 1; }
  .card-title { font-size: 14px; font-weight: 700; color: #e6edf3; }
  .card-desc { font-size: 12px; color: #8b949e; line-height: 1.5; }
  .card-arrow { margin-top: auto; padding-top: 8px; font-size: 12px; color: #58a6ff; font-weight: 600; }

  .refs {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(185px, 1fr));
    gap: 10px;
    margin-bottom: 48px;
  }
  .ref-item {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 14px 16px;
    text-decoration: none !important;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: border-color .15s;
  }
  .ref-item:hover { border-color: #58a6ff; }
  .ref-name { font-size: 13px; font-weight: 600; color: #58a6ff; }
  .ref-desc { font-size: 12px; color: #8b949e; line-height: 1.4; }

  .stack {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding-top: 32px;
    border-top: 1px solid #21262d;
  }
  .badge {
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 6px;
    background: #21262d;
    color: #8b949e;
    border: 1px solid #30363d;
  }
</style>

<div class="hero">
  <div class="hero-badge">MLH Production Engineering Hackathon</div>
  <h1>URL <span>Shortener</span></h1>
  <p class="hero-sub">A production-grade URL shortening service built with reliability, scalability, and observability from day one.</p>
  <div class="hero-btns">
    <a class="btn btn-green" href="https://github.com/RETR0-OS/MLH_PE_URL_Shortener" target="_blank">⭐ GitHub Repo</a>
    <a class="btn btn-dark" href="{{ site.baseurl }}/api">📄 API Docs</a>
  </div>
</div>

<div class="section-label">Tracks</div>
<div class="tracks">
  <a class="card" href="{{ site.baseurl }}/Reliability/RELIABILITY_ENGINEERING">
    <div class="card-icon">🛡️</div>
    <div class="card-title">Reliability Engineering</div>
    <div class="card-desc">CI/CD pipeline, 91% test coverage, chaos engineering, container restart policies, and failure modes.</div>
    <div class="card-arrow">Read docs →</div>
  </a>
  <a class="card" href="{{ site.baseurl }}/TRACK2_SCALABILITY_ENGINEERING">
    <div class="card-icon">🚀</div>
    <div class="card-title">Scalability Engineering</div>
    <div class="card-desc">500 VU k6 load tests, Nginx load balancing, Redis caching, horizontal scaling, and bottleneck analysis.</div>
    <div class="card-arrow">Read docs →</div>
  </a>
  <a class="card" href="{{ site.baseurl }}/TRACK3_INCIDENT_RESPONSE">
    <div class="card-icon">🚨</div>
    <div class="card-title">Incident Response</div>
    <div class="card-desc">Prometheus alerting, Grafana dashboards, Loki log aggregation, Jaeger tracing, and RCA documentation.</div>
    <div class="card-arrow">Read docs →</div>
  </a>
  <a class="card" href="{{ site.baseurl }}/TRACK4_DOCUMENTATION">
    <div class="card-icon">📜</div>
    <div class="card-title">Documentation</div>
    <div class="card-desc">Architecture diagrams, API docs, deploy guide, runbook, decision log, and capacity plan.</div>
    <div class="card-arrow">Read docs →</div>
  </a>
</div>

<div class="section-label">Reference Docs</div>
<div class="refs">
  <a class="ref-item" href="{{ site.baseurl }}/DEPLOYMENT">
    <div class="ref-name">Deploy Guide</div>
    <div class="ref-desc">How to deploy and rollback</div>
  </a>
  <a class="ref-item" href="{{ site.baseurl }}/ARCHITECTURE">
    <div class="ref-name">Architecture</div>
    <div class="ref-desc">System design and component diagram</div>
  </a>
  <a class="ref-item" href="{{ site.baseurl }}/Reliability/RELIABILITY_ENGINEERING#failure-modes-documentation">
    <div class="ref-name">Failure Modes</div>
    <div class="ref-desc">Every failure, detection, and recovery</div>
  </a>
  <a class="ref-item" href="{{ site.baseurl }}/Reliability/RELIABILITY_ENGINEERING#error-handling-documentation">
    <div class="ref-name">Error Handling</div>
    <div class="ref-desc">All error codes and response shapes</div>
  </a>
  <a class="ref-item" href="{{ site.baseurl }}/TRACK4_DOCUMENTATION#decision-log">
    <div class="ref-name">Decision Log</div>
    <div class="ref-desc">Why we chose Redis, Nginx, Gunicorn</div>
  </a>
  <a class="ref-item" href="{{ site.baseurl }}/TRACK2_SCALABILITY_ENGINEERING#bottleneck-analysis">
    <div class="ref-name">Bottleneck Report</div>
    <div class="ref-desc">What was slow and how we fixed it</div>
  </a>
  <a class="ref-item" href="{{ site.baseurl }}/api">
    <div class="ref-name">API Docs</div>
    <div class="ref-desc">Interactive Swagger UI</div>
  </a>
</div>

<div class="section-label">Tech Stack</div>
<div class="stack">
  <span class="badge">Python / Flask</span>
  <span class="badge">PostgreSQL</span>
  <span class="badge">Redis</span>
  <span class="badge">Nginx</span>
  <span class="badge">Docker Compose</span>
  <span class="badge">Prometheus</span>
  <span class="badge">Grafana</span>
  <span class="badge">Loki</span>
  <span class="badge">Alertmanager</span>
  <span class="badge">Jaeger</span>
  <span class="badge">k6</span>
  <span class="badge">pytest</span>
  <span class="badge">GitHub Actions</span>
  <span class="badge">Trivy</span>
</div>
