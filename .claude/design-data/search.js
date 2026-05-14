#!/usr/bin/env node
// Design Intelligence Search Engine — BM25 for UI/UX decisions
// Ported from ui-ux-pro-max-skill (Python) to Node.js
// Usage:
//   node search.js "<query>"                          # auto-detect domain
//   node search.js "<query>" --domain style           # specific domain
//   node search.js "<query>" --design-system          # full recommendation
//   node search.js "<query>" --design-system -p "Name"

const fs = require("fs");
const path = require("path");

const DATA_DIR = __dirname;
const MAX_RESULTS = 3;

// ============ CSV CONFIG ============
const CSV_CONFIG = {
  style: {
    file: "styles.csv",
    searchCols: ["Style Category", "Keywords", "Best For", "Type", "AI Prompt Keywords"],
    outputCols: ["Style Category", "Type", "Keywords", "Primary Colors", "Effects & Animation", "Best For", "Light Mode \u2713", "Dark Mode \u2713", "Performance", "Accessibility", "CSS/Technical Keywords", "Design System Variables"],
  },
  color: {
    file: "colors.csv",
    searchCols: ["Product Type", "Notes"],
    outputCols: ["Product Type", "Primary", "On Primary", "Secondary", "On Secondary", "Accent", "On Accent", "Background", "Foreground", "Card", "Card Foreground", "Muted", "Muted Foreground", "Border", "Destructive", "Ring", "Notes"],
  },
  chart: {
    file: "charts.csv",
    searchCols: ["Data Type", "Keywords", "Best Chart Type", "When to Use", "When NOT to Use"],
    outputCols: ["Data Type", "Keywords", "Best Chart Type", "Secondary Options", "When to Use", "When NOT to Use", "Data Volume Threshold", "Color Guidance", "Accessibility Grade", "Accessibility Notes", "A11y Fallback", "Library Recommendation"],
  },
  landing: {
    file: "landing.csv",
    searchCols: ["Pattern Name", "Keywords", "Conversion Optimization", "Section Order"],
    outputCols: ["Pattern Name", "Keywords", "Section Order", "Primary CTA Placement", "Color Strategy", "Conversion Optimization"],
  },
  product: {
    file: "products.csv",
    searchCols: ["Product Type", "Keywords", "Primary Style Recommendation", "Key Considerations"],
    outputCols: ["Product Type", "Keywords", "Primary Style Recommendation", "Secondary Styles", "Landing Page Pattern", "Dashboard Style (if applicable)", "Color Palette Focus"],
  },
  ux: {
    file: "ux-guidelines.csv",
    searchCols: ["Category", "Issue", "Description", "Platform"],
    outputCols: ["Category", "Issue", "Platform", "Description", "Do", "Don't", "Severity"],
  },
  typography: {
    file: "typography.csv",
    searchCols: ["Font Pairing Name", "Category", "Mood/Style Keywords", "Best For", "Heading Font", "Body Font"],
    outputCols: ["Font Pairing Name", "Category", "Heading Font", "Body Font", "Mood/Style Keywords", "Best For", "Google Fonts URL", "CSS Import", "Tailwind Config"],
  },
  reasoning: {
    file: "ui-reasoning.csv",
    searchCols: ["UI_Category"],
    outputCols: ["UI_Category", "Recommended_Pattern", "Style_Priority", "Color_Mood", "Typography_Mood", "Key_Effects", "Decision_Rules", "Anti_Patterns", "Severity"],
  },
};

// ============ CSV PARSER ============
function parseCSV(text) {
  const lines = text.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];
  const headers = parseCSVLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row = {};
    headers.forEach((h, idx) => (row[h] = values[idx] || ""));
    rows.push(row);
  }
  return rows;
}

function parseCSVLine(line) {
  const result = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        current += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        current += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        result.push(current.trim());
        current = "";
      } else {
        current += ch;
      }
    }
  }
  result.push(current.trim());
  return result;
}

function loadCSV(filename) {
  const filepath = path.join(DATA_DIR, filename);
  if (!fs.existsSync(filepath)) return [];
  return parseCSV(fs.readFileSync(filepath, "utf8"));
}

// ============ BM25 IMPLEMENTATION ============
class BM25 {
  constructor(k1 = 1.5, b = 0.75) {
    this.k1 = k1;
    this.b = b;
    this.corpus = [];
    this.docLengths = [];
    this.avgdl = 0;
    this.idf = {};
    this.docFreqs = {};
    this.N = 0;
  }

  tokenize(text) {
    return String(text)
      .toLowerCase()
      .replace(/[^\w\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2);
  }

  fit(documents) {
    this.corpus = documents.map((d) => this.tokenize(d));
    this.N = this.corpus.length;
    if (this.N === 0) return;
    this.docLengths = this.corpus.map((d) => d.length);
    this.avgdl = this.docLengths.reduce((a, b) => a + b, 0) / this.N;

    this.docFreqs = {};
    for (const doc of this.corpus) {
      const seen = new Set();
      for (const word of doc) {
        if (!seen.has(word)) {
          this.docFreqs[word] = (this.docFreqs[word] || 0) + 1;
          seen.add(word);
        }
      }
    }

    this.idf = {};
    for (const [word, freq] of Object.entries(this.docFreqs)) {
      this.idf[word] = Math.log((this.N - freq + 0.5) / (freq + 0.5) + 1);
    }
  }

  score(query) {
    const queryTokens = this.tokenize(query);
    const scores = [];

    for (let idx = 0; idx < this.corpus.length; idx++) {
      let score = 0;
      const doc = this.corpus[idx];
      const docLen = this.docLengths[idx];
      const termFreqs = {};
      for (const word of doc) {
        termFreqs[word] = (termFreqs[word] || 0) + 1;
      }

      for (const token of queryTokens) {
        if (this.idf[token] !== undefined) {
          const tf = termFreqs[token] || 0;
          const idfVal = this.idf[token];
          const numerator = tf * (this.k1 + 1);
          const denominator = tf + this.k1 * (1 - this.b + (this.b * docLen) / this.avgdl);
          score += idfVal * (numerator / denominator);
        }
      }

      scores.push([idx, score]);
    }

    return scores.sort((a, b) => b[1] - a[1]);
  }
}

// ============ SEARCH FUNCTIONS ============
function searchCSV(filename, searchCols, outputCols, query, maxResults) {
  const data = loadCSV(filename);
  if (data.length === 0) return [];

  const documents = data.map((row) => searchCols.map((col) => row[col] || "").join(" "));

  const bm25 = new BM25();
  bm25.fit(documents);
  const ranked = bm25.score(query);

  const results = [];
  for (const [idx, score] of ranked.slice(0, maxResults)) {
    if (score > 0) {
      const row = data[idx];
      const out = {};
      for (const col of outputCols) {
        if (row[col] !== undefined) out[col] = row[col];
      }
      results.push(out);
    }
  }
  return results;
}

const DOMAIN_KEYWORDS = {
  color: ["color", "palette", "hex", "rgb", "token", "semantic", "accent", "destructive", "muted"],
  chart: ["chart", "graph", "visualization", "trend", "bar", "pie", "scatter", "heatmap", "funnel"],
  landing: ["landing", "page", "cta", "conversion", "hero", "testimonial", "pricing", "section"],
  product: [
    "saas", "ecommerce", "fintech", "healthcare", "gaming", "portfolio", "crypto", "dashboard",
    "fitness", "restaurant", "hotel", "travel", "music", "education", "legal", "insurance",
    "medical", "beauty", "pharmacy", "dental", "pet", "dating", "wedding", "delivery",
    "booking", "tracker", "diary", "chat", "crm", "invoice", "vpn", "weather", "meditation",
    "habit", "grocery", "photography", "streaming", "podcast", "newsletter", "marketplace",
    "freelancer", "coworking", "airline", "museum", "church", "charity", "kindergarten",
    "veterinary", "florist", "bakery", "brewery", "construction", "automotive", "real estate",
    "logistics", "agriculture", "spa", "wellness", "luxury",
  ],
  style: ["style", "design", "ui", "minimalism", "glassmorphism", "neumorphism", "brutalism", "dark mode", "flat", "aurora"],
  ux: ["ux", "usability", "accessibility", "wcag", "touch", "scroll", "animation", "keyboard", "navigation"],
  typography: ["font", "typography", "heading font", "body font", "serif", "sans"],
};

function detectDomain(query) {
  const q = query.toLowerCase();
  const scores = {};
  for (const [domain, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
    scores[domain] = keywords.filter((kw) => q.includes(kw)).length;
  }
  const best = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
  return best && best[1] > 0 ? best[0] : "product";
}

function search(query, domain, maxResults = MAX_RESULTS) {
  if (!domain) domain = detectDomain(query);
  const config = CSV_CONFIG[domain] || CSV_CONFIG.product;
  const results = searchCSV(config.file, config.searchCols, config.outputCols, query, maxResults);
  return { domain, query, file: config.file, count: results.length, results };
}

// ============ DESIGN SYSTEM GENERATOR ============
function findReasoningRule(category) {
  const data = loadCSV("ui-reasoning.csv");
  const catLow = category.toLowerCase();

  // Exact match
  let rule = data.find((r) => (r.UI_Category || "").toLowerCase() === catLow);
  if (rule) return rule;

  // Partial match
  rule = data.find((r) => {
    const ui = (r.UI_Category || "").toLowerCase();
    return ui.includes(catLow) || catLow.includes(ui);
  });
  if (rule) return rule;

  // Keyword match
  rule = data.find((r) => {
    const keywords = (r.UI_Category || "").toLowerCase().replace(/[\/\-]/g, " ").split(/\s+/);
    return keywords.some((kw) => kw.length > 3 && catLow.includes(kw));
  });
  return rule || null;
}

function applyReasoning(category) {
  const rule = findReasoningRule(category);
  if (!rule) {
    return {
      pattern: "Hero + Features + CTA",
      stylePriority: ["Minimalism", "Flat Design"],
      colorMood: "Professional",
      typographyMood: "Clean",
      keyEffects: "Subtle hover transitions",
      antiPatterns: "",
      decisionRules: {},
      severity: "MEDIUM",
    };
  }

  let decisionRules = {};
  try {
    decisionRules = JSON.parse(rule.Decision_Rules || "{}");
  } catch (_) {}

  return {
    pattern: rule.Recommended_Pattern || "",
    stylePriority: (rule.Style_Priority || "").split("+").map((s) => s.trim()),
    colorMood: rule.Color_Mood || "",
    typographyMood: rule.Typography_Mood || "",
    keyEffects: rule.Key_Effects || "",
    antiPatterns: rule.Anti_Patterns || "",
    decisionRules,
    severity: rule.Severity || "MEDIUM",
  };
}

function selectBestMatch(results, priorityKeywords) {
  if (!results.length) return {};
  if (!priorityKeywords || !priorityKeywords.length) return results[0];

  // Exact style name match
  for (const priority of priorityKeywords) {
    const pLow = priority.toLowerCase().trim();
    for (const result of results) {
      const styleName = (result["Style Category"] || "").toLowerCase();
      if (pLow.includes(styleName) || styleName.includes(pLow)) return result;
    }
  }

  // Score by keyword match
  const scored = results.map((result) => {
    const resultStr = JSON.stringify(result).toLowerCase();
    let score = 0;
    for (const kw of priorityKeywords) {
      const kwLow = kw.toLowerCase().trim();
      if ((result["Style Category"] || "").toLowerCase().includes(kwLow)) score += 10;
      else if ((result["Keywords"] || "").toLowerCase().includes(kwLow)) score += 3;
      else if (resultStr.includes(kwLow)) score += 1;
    }
    return { score, result };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored[0].score > 0 ? scored[0].result : results[0];
}

function generateDesignSystem(query, projectName) {
  // Step 1: Find product category
  const productResult = search(query, "product", 1);
  const category = productResult.results.length > 0 ? productResult.results[0]["Product Type"] || "General" : "General";

  // Step 2: Get reasoning rules
  const reasoning = applyReasoning(category);

  // Step 3: Multi-domain search
  const styleQuery = reasoning.stylePriority.length ? `${query} ${reasoning.stylePriority.slice(0, 2).join(" ")}` : query;
  const styleResult = search(styleQuery, "style", 3);
  const colorResult = search(query, "color", 2);
  const typographyResult = search(query, "typography", 2);
  const landingResult = search(query, "landing", 2);

  // Step 4: Select best matches
  const bestStyle = selectBestMatch(styleResult.results, reasoning.stylePriority);
  const bestColor = colorResult.results[0] || {};
  const bestTypo = typographyResult.results[0] || {};
  const bestLanding = landingResult.results[0] || {};

  // Step 5: Build recommendation
  const styleEffects = bestStyle["Effects & Animation"] || "";
  const combinedEffects = styleEffects || reasoning.keyEffects;

  return {
    project_name: projectName || query.toUpperCase(),
    category,
    pattern: {
      name: bestLanding["Pattern Name"] || reasoning.pattern,
      sections: bestLanding["Section Order"] || "Hero > Features > CTA",
      cta_placement: bestLanding["Primary CTA Placement"] || "Above fold",
      color_strategy: bestLanding["Color Strategy"] || "",
      conversion: bestLanding["Conversion Optimization"] || "",
    },
    style: {
      name: bestStyle["Style Category"] || "Minimalism",
      type: bestStyle["Type"] || "General",
      effects: styleEffects,
      keywords: bestStyle["Keywords"] || "",
      best_for: bestStyle["Best For"] || "",
      performance: bestStyle["Performance"] || "",
      accessibility: bestStyle["Accessibility"] || "",
      css_keywords: bestStyle["CSS/Technical Keywords"] || "",
      design_variables: bestStyle["Design System Variables"] || "",
    },
    colors: {
      primary: bestColor["Primary"] || "#2563EB",
      on_primary: bestColor["On Primary"] || "#FFFFFF",
      secondary: bestColor["Secondary"] || "#3B82F6",
      on_secondary: bestColor["On Secondary"] || "#FFFFFF",
      accent: bestColor["Accent"] || "#F97316",
      on_accent: bestColor["On Accent"] || "#FFFFFF",
      background: bestColor["Background"] || "#F8FAFC",
      foreground: bestColor["Foreground"] || "#1E293B",
      muted: bestColor["Muted"] || "",
      border: bestColor["Border"] || "",
      destructive: bestColor["Destructive"] || "",
      ring: bestColor["Ring"] || "",
      notes: bestColor["Notes"] || "",
    },
    typography: {
      heading: bestTypo["Heading Font"] || "Inter",
      body: bestTypo["Body Font"] || "Inter",
      mood: bestTypo["Mood/Style Keywords"] || reasoning.typographyMood,
      best_for: bestTypo["Best For"] || "",
      google_fonts_url: bestTypo["Google Fonts URL"] || "",
      css_import: bestTypo["CSS Import"] || "",
    },
    key_effects: combinedEffects,
    anti_patterns: reasoning.antiPatterns,
    decision_rules: reasoning.decisionRules,
    severity: reasoning.severity,
    color_mood: reasoning.colorMood,
    typography_mood: reasoning.typographyMood,
  };
}

// ============ CLI ============
function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("Usage: node search.js <query> [--domain <domain>] [--design-system] [-p <project>]");
    console.error("Domains: style, color, chart, landing, product, ux, typography");
    process.exit(1);
  }

  const query = args[0];
  let domain = null;
  let designSystem = false;
  let projectName = null;
  let maxResults = MAX_RESULTS;

  for (let i = 1; i < args.length; i++) {
    if (args[i] === "--domain" || args[i] === "-d") domain = args[++i];
    else if (args[i] === "--design-system" || args[i] === "-ds") designSystem = true;
    else if (args[i] === "-p" || args[i] === "--project-name") projectName = args[++i];
    else if (args[i] === "-n" || args[i] === "--max-results") maxResults = parseInt(args[++i]);
  }

  if (designSystem) {
    const result = generateDesignSystem(query, projectName);
    console.log(JSON.stringify(result, null, 2));
  } else {
    const result = search(query, domain, maxResults);
    console.log(JSON.stringify(result, null, 2));
  }
}

main();
