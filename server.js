const http = require('http');
const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

const PORT = 5000;
const HOST = '0.0.0.0';

function readFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return null;
  }
}

function renderPage(title, markdownContent, lang) {
  const html = marked.parse(markdownContent);
  return `<!DOCTYPE html>
<html lang="${lang || 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <meta name="description" content="Clavo is your personalized AI Companion and TavernAI roleplay bot across WeChat, Telegram, and WhatsApp.">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      min-height: 100vh;
      color: #e0e0e0;
      line-height: 1.7;
    }
    header {
      background: rgba(255,255,255,0.05);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(255,255,255,0.1);
      padding: 16px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header .logo {
      font-size: 1.5rem;
      font-weight: 700;
      color: #a78bfa;
      text-decoration: none;
    }
    header nav a {
      color: #c4b5fd;
      text-decoration: none;
      margin-left: 20px;
      font-size: 0.95rem;
      transition: color 0.2s;
    }
    header nav a:hover { color: #fff; }
    .container {
      max-width: 860px;
      margin: 40px auto;
      padding: 0 24px;
    }
    .card {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 16px;
      padding: 40px;
      backdrop-filter: blur(10px);
    }
    .card h1 {
      font-size: 2rem;
      font-weight: 700;
      color: #a78bfa;
      margin-bottom: 16px;
    }
    .card h2 {
      font-size: 1.4rem;
      font-weight: 600;
      color: #c4b5fd;
      margin: 28px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(167,139,250,0.3);
    }
    .card h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #ddd6fe;
      margin: 20px 0 8px;
    }
    .card p { margin: 10px 0; color: #d1d5db; }
    .card a { color: #a78bfa; text-decoration: none; }
    .card a:hover { text-decoration: underline; }
    .card ul, .card ol {
      padding-left: 24px;
      margin: 10px 0;
    }
    .card li { margin: 6px 0; color: #d1d5db; }
    .card blockquote {
      border-left: 3px solid #a78bfa;
      padding: 12px 20px;
      margin: 16px 0;
      background: rgba(167,139,250,0.08);
      border-radius: 0 8px 8px 0;
      color: #c4b5fd;
    }
    .card code {
      background: rgba(167,139,250,0.15);
      color: #ddd6fe;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Courier New', monospace;
      font-size: 0.9em;
    }
    .card pre {
      background: rgba(0,0,0,0.3);
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      margin: 16px 0;
    }
    .card pre code { background: none; padding: 0; }
    .card strong { color: #e9d5ff; }
    footer {
      text-align: center;
      padding: 32px;
      color: #6b7280;
      font-size: 0.85rem;
    }
    footer a { color: #a78bfa; text-decoration: none; }
  </style>
</head>
<body>
  <header>
    <a class="logo" href="/">🤖 Clavo</a>
    <nav>
      <a href="/">English</a>
      <a href="/zh-CN">简体中文</a>
      <a href="https://clavo.chat" target="_blank">Official Site ↗</a>
    </nav>
  </header>
  <div class="container">
    <div class="card">
      ${html}
    </div>
  </div>
  <footer>
    <p>© 2024 <a href="https://clavo.chat">Clavo</a> — AI Companion & TavernAI Roleplay Bot</p>
  </footer>
</body>
</html>`;
}

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];

  if (url === '/zh-CN' || url === '/zh-cn' || url === '/README.zh-CN' || url === '/README.zh-CN.md') {
    const content = readFile(path.join(__dirname, 'README.zh-CN.md'));
    if (content) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(renderPage('Clavo - AI 伴侣 & TavernAI 角色扮演机器人', content, 'zh-CN'));
      return;
    }
  }

  if (url === '/' || url === '/index.html' || url === '/README' || url === '/README.md') {
    const content = readFile(path.join(__dirname, 'README.md'));
    if (content) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(renderPage('Clavo - AI Companion & TavernAI Roleplay Bot', content, 'en'));
      return;
    }
  }

  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

server.listen(PORT, HOST, () => {
  console.log(`Clavo site running at http://${HOST}:${PORT}`);
});
