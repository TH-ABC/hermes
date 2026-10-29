const fs = require('fs');
const html = fs.readFileSync('D:/hermes-main/hermes-agent-vercel/public/app.html', 'utf8');
const scriptMatches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
console.log(`Found ${scriptMatches.length} script tags`);
for (let i = 0; i < scriptMatches.length; i++) {
  try {
    const code = scriptMatches[i][1];
    // Mock browser globals
    const window = { addEventListener: () => {} };
    const document = { querySelectorAll: () => [], getElementById: () => ({ innerText: '', innerHTML: '', classList: { add: () => {}, remove: () => {} } }) };
    const lucide = { createIcons: () => {} };
    const alert = () => {};
    const XLSX = {};
    eval(code);
    console.log(`Script tag ${i + 1}: SYNTAX OK!`);
  } catch (err) {
    console.error(`Script tag ${i + 1} ERROR:`, err);
    process.exit(1);
  }
}
