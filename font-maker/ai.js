// Changing the font by asking in words. The built-in assistant understands requests here, with no
// key and no internet. With an Anthropic API key, Claude reads any request and answers with the new
// settings (through a tool whose input is the settings).
(function () {
  "use strict";

  const MODEL = "claude-opus-5-5";

  // ---------------------------------------------------------------- the built-in assistant
  //
  // It runs here, without internet and without a key. It is not a language model: it knows the
  // words people use for the shape of letters (in many forms: "עבה", "תעבה", "להעבות", "יותר עובי"),
  // how much ("קצת", "מאוד", "ב־20%", "פי 2", "10 מעלות"), about what (the whole font, "האות ש",
  // "הסופיות"), styles ("לכותרת", "לילדים", "אלגנטי"), going back ("תחזיר", "בטל"), and changing
  // to another font of the library ("תחליף לחיבו"). It forgives small spelling mistakes.

  // words for a setting and the way they push it: +1 more, -1 less, 0 back to normal
  const LEX = [
    ["weight", 1, "עבה עבות עבים עבי מעובה תעבה תעבי להעבות העבה מודגש מודגשת מודגשות בולד בולט בולטת כבד כבדה כבדות שמן שמנה שמנות חזק חזקה כהה כהות שחור עובי"],
    ["weight", -1, "דק דקה דקות דקים תדק תדקק להדק רזה רזות תרזה עדין עדינה עדינות קל קלה קלות בהיר בהירה לייט אוורירי"],
    ["width", 1, "רחב רחבה רחבות רחבים תרחיב תרחיבי להרחיב הרחב מורחב מורחבת רוחב"],
    ["width", -1, "צר צרה צרות צרים תצר תצרי להצר דחוס דחוסה דחוסות תדחוס צפוף-אותיות מוצר"],
    ["height", 1, "גבוה גבוהה גבוהות גבוהים תגביה להגביה גובה גדול גדולה גדולות"],
    ["height", -1, "נמוך נמוכה נמוכות נמוכים תנמיך להנמיך קטן קטנה קטנות שטוח שטוחה"],
    ["depth", 1, "ארוך ארוכה ארוכות ארוכים תאריך להאריך זנב זנבות"],
    ["depth", -1, "קצר קצרה קצרות קצרים תקצר לקצר"],
    ["slant", 1, "נטוי נטויה נטויות נוטה נוטות תטה להטות הטה אלכסוני אלכסונית איטלקי איטליק נטייה"],
    ["slant", 0, "ישר ישרה ישרות זקוף זקופה זקופות עומד"],
    ["round", 1, "עגול עגולה עגולות עגולים מעוגל מעוגלת מעוגלות תעגל לעגל רך רכה רכות רכים חמוד חמודה עיגול"],
    ["round", -1, "חד חדה חדות חדים מחודד מחודדת תחדד לחדד מרובע מרובעת זוויתי"],
    ["spacing", 1, "מרווח מרווחת מרווחות מרווחים פזור מפוזר תרווח לרווח ריווח רווח מפורד"],
    ["spacing", -1, "צפוף צפופה צפופות צמוד צמודה צמודות תצופף תקרב לקרב צמודים"],
    ["contrast", 1, "ניגודיות קונטרסט מנוגד"],
    ["contrast", 0, "אחיד אחידה אחידות"],
    ["shift", 1, "למעלה תעלה להעלות הרם"],
    ["shift", -1, "למטה תוריד-אותה תנמיך-אותה"],
  ];

  const MORE = "יותר הגדל תגדיל להגדיל הוסף תוסיף להוסיף העלה תעלה להעלות הגבר תגביר להגביר";
  const LESS = "פחות הקטן תקטין להקטין הורד תוריד להוריד הפחת תפחית להפחית צמצם תצמצם";
  const NONE = "בלי ללא אפס תבטל לבטל";
  const BACK = "תחזיר להחזיר החזר תחזירי איפוס אפס-הכל לאפס מקורי מקורית המקור כמקור רגיל רגילה";
  const UNDO = ["תבטל את זה", "בטל את זה", "בטל את השינוי", "תבטל את השינוי", "אחורה", "חזור אחורה", "לא אהבתי", "תחזיר את מה שהיה"];

  // styles: several settings at once, as a move of each (in steps)
  const STYLES = [
    ["כותרת כותרות לכותרת לכותרות לשלט שלט בולט-מאוד פוסטר", { weight: 2, spacing: -0.5 }],
    ["ילדים לילדים ילדותי ילדותית שמח שמחה חמוד חמודה כיף מצחיק מצחיקה", { round: 2, weight: 1 }],
    ["אלגנטי אלגנטית יוקרתי יוקרתית מעודן מעודנת חגיגי חגיגית", { weight: -1, spacing: 0.7, contrast: 1 }],
    ["מודרני מודרנית נקי נקייה מינימליסטי מינימליסטית טכנולוגי", { contrast: -1, round: -1 }],
    ["קלאסי קלאסית מסורתי מסורתית ספרותי ספרותית תורני ישן ישנה עתיק עתיקה", { contrast: 1.5 }],
    ["רציני רצינית רשמי רשמית מכובד מכובדת", { round: -2, slant: -9 }],
    ["כתב-יד בכתב-יד ידני ידנית זורם זורמת", { slant: 1, round: 1 }],
    ["קריא קריאה נוח-לקריאה לקריאה לספר לטקסט", { spacing: 0.7, weight: 0.5 }],
    ["חסכוני חסכונית לחסוך-מקום", { width: -1, spacing: -0.7 }],
  ];

  const GROUPS = [
    [/(?:ה)?(?:אותיות\s+)?(?:ה)?סופיות/, "ךםןףץ"],
    [/(?:ה)?אותיות\s+(?:ה)?יורדות|(?:ה)?זנבות/, "ךןףץק"],
    [/בג"?ד\s*כפ"?ת/, "בגדכפת"],
  ];
  const PREFIXES = ["וכש", "וש", "וה", "וב", "ול", "וכ", "ומ", "שה", "שב", "של", "שכ", "כש", "מה", "לה", "בה", "ו", "ה", "ב", "ל", "כ", "מ", "ש"];

  function levenshtein(a, b) {
    if (Math.abs(a.length - b.length) > 1) return 9;
    const d = [];
    for (let i = 0; i <= a.length; i++) { d[i] = [i]; }
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    return d[a.length][b.length];
  }

  const words = (list) => list.split(/\s+/).map((w) => w.replace(/-/g, " "));
  const LEXW = LEX.map(([key, dir, list]) => ({ key, dir, words: words(list) }));
  const STOP = new Set(words("את של הגופן גופן אותו אותה שיהיה שיהיו יותר פחות תעשה תעשי לעשות אני רוצה משהו מעלות אחוז האות האותיות אותיות קצת מאוד הרבה ממש בבקשה תודה כמו שזה עכשיו כל"));
  const ALL = new Map();
  LEXW.forEach((e) => e.words.forEach((w) => { if (!w.includes(" ")) ALL.set(w, e); }));

  // the setting a word speaks of, from its own form, without its prefix, or with one mistake
  function lookup(tok) {
    const tries = [tok];
    for (const p of PREFIXES) if (tok.startsWith(p) && tok.length - p.length >= 2) tries.push(tok.slice(p.length));
    for (const t of tries) if (ALL.has(t)) return ALL.get(t);
    // one spelling mistake, in a whole word that is not a common word
    if (tok.length >= 4 && !STOP.has(tok)) {
      for (const [w, e] of ALL) if (w.length >= 4 && levenshtein(tok, w) === 1) return e;
    }
    return null;
  }

  const has = (text, list) => words(list).some((w) => new RegExp("(^|[^א-ת])(ו|ה|ש|ל|ב|כ|מ)?" + w + "($|[^א-ת])").test(text));

  function clean(text) {
    return " " + text.replace(/[֑-ׇ]/g, "").replace(/[״"]/g, '"').replace(/[׳']/g, "'").replace(/[־–—]/g, "-") + " ";
  }

  // "האות ש", "את ה-ש", "האותיות ש, ל ו-מ", "'ש'", "הסופיות": the letters a request is about
  function lettersIn(t) {
    const out = [];
    for (const [re, letters] of GROUPS) if (re.test(t)) out.push(...letters);
    const re = /(?:(?:^|\s)(?:האותיות|האות|אותיות|אות)\s+|של ה-|את ה-|ב-?ה-|(?:^|\s)ה-|ל-ה?-?)((?:[א-ת](?=[\s,'"-]|$)(?:['"]|\s|,|ו-?|-)*)+)/g;
    let m;
    while ((m = re.exec(t))) {
      for (const ch of m[1].replace(/ו-?(?=[א-ת](?:[\s,'"]|$))/g, " ").split(/[\s,'"-]+/)) if (/^[א-ת]$/.test(ch)) out.push(ch);
    }
    const q = /'([א-ת])'/g;
    while ((m = q.exec(t))) out.push(m[1]);
    return [...new Set(out)];
  }

  // how much: a word, a number of percents, times, or degrees
  function amountIn(t) {
    const r = { times: 1, percent: null, factor: null, degrees: null, max: false };
    if (/מאוד|הרבה|ממש|בהרבה|לגמרי|משמעותית|חזק/.test(t)) r.times = 2;
    if (/קצת|מעט|טיפה|קצת-יותר|במעט|קצת יותר/.test(t)) r.times = 0.5;
    if (/הכי|מקסימום|מקסימלי|עד הסוף/.test(t)) r.max = true;
    let m = t.match(/(\d+(?:\.\d+)?)\s*(?:%|אחוז)/);
    if (m) r.percent = Number(m[1]);
    m = t.match(/פי\s*(\d+(?:\.\d+)?)/);
    if (m) r.factor = Number(m[1]);
    if (/בחצי|לחצי|חצי/.test(t)) r.factor = r.factor || 0.5;
    m = t.match(/(\d+(?:\.\d+)?)\s*מעלות/);
    if (m) r.degrees = Number(m[1]);
    return r;
  }

  function fontIn(t, fonts) {
    if (!fonts || !/תחליף|תעבור|החלף|לעבור|מבוסס|גופן\s|תתחיל|כמו\s/.test(t)) return null;
    let best = null;
    for (const f of fonts) {
      for (const n of [f.name, f.id, f.family].filter(Boolean)) {
        const nn = String(n).replace(/[״"]/g, "").toLowerCase();
        const tt = t.replace(/[״"]/g, "").toLowerCase();
        if (nn.length >= 2 && tt.includes(nn) && (!best || nn.length > best.len)) best = { id: f.id, name: f.name, len: nn.length };
        const first = nn.split(/[\s-]/)[0];
        if (!best && first.length >= 3 && tt.includes(first)) best = { id: f.id, name: f.name, len: first.length };
      }
    }
    return best;
  }

  // ctx: {keys: [{key, label, min, max, step, value, neutral}], letterKeys: [{key, label, min, max, step, base}] | null,
  //       letterValue(letter, key), fonts: [{id, name, family}]}
  function simple(text, ctx) {
    const out = { settings: [], letters: [], explanation: "", font: null, undo: false };
    const all = clean(text);
    if (UNDO.some((u) => all.includes(u))) { out.undo = true; out.explanation = "מבטל את השינוי האחרון."; return out; }
    const font = fontIn(all, ctx.fonts);
    if (font) out.font = font;
    // each part on its own: "עבה יותר, והאות ש רחבה" is two changes
    const parts = all.split(/[,.;!?\n]+| ו(?=(?:האות|האותיות|את ה|ה-|הסופיות))| אבל /).filter((p) => p.trim());
    const set = {}, lset = {};
    for (const p of parts) part(clean(p), ctx, set, lset);
    for (const k in set) out.settings.push({ key: k, value: set[k] });
    for (const id in lset) { const [letter, key] = id.split("|"); out.letters.push({ letter, key, value: lset[id] }); }
    if (!out.settings.length && !out.letters.length && !out.font) {
      out.explanation = "לא הבנתי מה לשנות. אפשר לכתוב למשל: \"עבה יותר\", \"צר קצת\", \"נטוי ב-10 מעלות\", \"עגול מאוד\", " +
        "\"האות ש רחבה יותר\", \"הסופיות ארוכות יותר\", \"תעשה אותו מתאים לכותרת\", \"תחזיר את הרוחב\", \"תחליף לחיבו\".";
    } else out.explanation = "הבנתי: " + understood(out, ctx);
    return out;
  }

  function part(t, ctx, set, lset) {
    const amt = amountIn(t);
    const more = has(t, MORE), less = has(t, LESS), none = has(t, NONE), back = has(t, BACK);
    let letters = ctx.letterKeys ? lettersIn(t) : [];
    const found = [];
    // the words of the request, one by one
    for (const tok of t.split(/[^א-ת"'-]+/).filter(Boolean)) {
      if (STOP.has(tok)) continue;
      const e = lookup(tok.replace(/["'-]/g, ""));
      if (e && !found.some((f) => f.key === e.key)) found.push({ key: e.key, dir: e.dir });
    }
    // two-word phrases ("כתב יד", "נוח לקריאה") are in the styles
    for (const [list, moves] of STYLES) {
      if (has(t, list)) for (const k in moves) if (!found.some((f) => f.key === k)) found.push({ key: k, dir: Math.sign(moves[k]), mult: Math.abs(moves[k]) });
    }
    // tails belong to letters: with no letter named, the letters that have one
    if (ctx.letterKeys && !letters.length && found.some((f) => f.key === "depth")) letters = [..."ךןףץק"];
    // "תחזיר את הכל" / "כמו המקור" with no setting: every setting back
    if (back && !found.length && !letters.length) {
      for (const k of ctx.keys) set[k.key] = k.neutral;
      return;
    }
    for (const f of found) {
      let dir = f.dir;
      if (less && dir !== 0) dir = -dir;
      else if (less && dir === 0) dir = -1;
      if (more && dir === 0) dir = 1;
      const toNeutral = back || (none && f.dir !== -1) || (f.dir === 0 && !more && !less);
      if (letters.length) {
        const lk = ctx.letterKeys.find((k) => k.key === f.key);
        if (!lk) continue;
        for (const L of letters) {
          const now = lset[L + "|" + f.key] !== undefined ? lset[L + "|" + f.key] : ctx.letterValue(L, f.key);
          lset[L + "|" + f.key] = newValue(lk, now, dir, amt, f.mult, toNeutral, lk.base, true);
        }
      } else {
        const k = ctx.keys.find((x) => x.key === f.key);
        if (!k) continue;
        const now = set[f.key] !== undefined ? set[f.key] : k.value;
        set[f.key] = newValue(k, now, dir, amt, f.mult, toNeutral, k.neutral, false);
      }
    }
  }

  function newValue(k, now, dir, amt, mult, toNeutral, neutral, isLetter) {
    if (toNeutral) return neutral;
    if (amt.max) return dir > 0 ? k.max : dir < 0 ? k.min : neutral;
    if (k.key === "slant" && amt.degrees !== null) return clamp(dir < 0 ? -amt.degrees : amt.degrees, k.min, k.max);
    const multiplicative = ["width", "height", "spacing"].includes(k.key) || (isLetter && k.base === 1);
    if (amt.factor !== null) {
      if (multiplicative) return clamp(dir < 0 ? now / amt.factor : now * amt.factor, k.min, k.max);
      return clamp(now + dir * k.step * amt.factor, k.min, k.max);
    }
    if (amt.percent !== null) {
      if (multiplicative) return clamp(now * (1 + (dir || 1) * amt.percent / 100), k.min, k.max);
      return clamp(now + (dir || 1) * (k.max - k.min) * amt.percent / 100, k.min, k.max);
    }
    // a slant asked for with no number: a usual italic angle
    if (k.key === "slant" && dir > 0 && Math.abs(now) < 0.5) return clamp(8 * amt.times * (mult || 1), k.min, k.max);
    return clamp(now + dir * k.step * amt.times * (mult || 1), k.min, k.max);
  }

  function understood(out, ctx) {
    const parts = [];
    if (out.font) parts.push("לעבור לגופן " + out.font.name);
    for (const c of out.settings) {
      const k = ctx.keys.find((x) => x.key === c.key);
      parts.push((k ? k.label : c.key) + " " + (k && k.fmt ? k.fmt(c.value) : c.value));
    }
    const same = new Map();
    for (const c of out.letters) {
      const k = ctx.letterKeys.find((x) => x.key === c.key);
      const t = (k ? k.label : c.key) + " " + (k && k.fmt ? k.fmt(c.value) : c.value);
      same.set(t, (same.get(t) || []).concat(c.letter));
    }
    for (const [t, ls] of same) parts.push(ls.join(" ") + ": " + t);
    return parts.join(", ") + ".";
  }

  function clamp(v, a, b) { return Math.min(b, Math.max(a, Math.round(v * 1000) / 1000)); }

  // ---------------------------------------------------------------- Claude

  function tool(ctx) {
    const props = {
      explanation: { type: "string", description: "One or two short sentences in Hebrew: what you changed and why." },
      settings: {
        type: "array",
        description: "Settings of the whole font to change, with their new values. Leave out settings that stay as they are.",
        items: {
          type: "object",
          properties: {
            key: { type: "string", enum: ctx.keys.map((k) => k.key) },
            value: { type: "number" },
          },
          required: ["key", "value"],
          additionalProperties: false,
        },
      },
      letters: {
        type: "array",
        description: ctx.letterKeys ? "Changes to single letters, with their new values. Empty when the request is about the whole font." : "Always empty in this mode.",
        items: {
          type: "object",
          properties: {
            letter: { type: "string", description: "One Hebrew letter, like ש or ך." },
            key: { type: "string", enum: (ctx.letterKeys || [{ key: "width" }]).map((k) => k.key) },
            value: { type: "number" },
          },
          required: ["letter", "key", "value"],
          additionalProperties: false,
        },
      },
    };
    return {
      name: "set_font",
      description: "Change the font being designed. Call it once with every change the request asks for.",
      strict: true,
      input_schema: { type: "object", properties: props, required: ["explanation", "settings", "letters"], additionalProperties: false },
    };
  }

  function describe(ctx) {
    const lines = ctx.keys.map((k) => `- ${k.key} (${k.label}): now ${k.value}, from ${k.min} to ${k.max}. ${k.about || ""}`);
    let s = "Settings of the whole font:\n" + lines.join("\n");
    if (ctx.letterKeys) {
      s += "\n\nSettings of a single letter (they multiply or add to the settings of the whole font):\n" +
        ctx.letterKeys.map((k) => `- ${k.key} (${k.label}): from ${k.min} to ${k.max}, ${k.base} means no change. ${k.about || ""}`).join("\n");
      const now = ctx.letterNow();
      if (now) s += "\n\nLetters already changed: " + now;
    }
    return s;
  }

  const SYSTEM = `You help a person who is not a type designer change a Hebrew font in a font maker program.
They write in Hebrew what they want changed; you call the set_font tool with the new values of the settings.

Change only what they asked for, and keep the font looking like a normal, readable font: unless they ask
for a strong change ("מאוד", "הרבה"), move a setting about a quarter of the way toward its end of the range.
"More" or "less" of something is relative to the value it has now. A request about some letters changes
only those letters. When a request can't be done with these settings, change nothing, and say in the
explanation what can be done instead.`;

  async function ask(text, ctx, apiKey, history) {
    const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });
    const before = (history || []).slice(-4).map((h) => `Earlier request: ${h.text}\nWhat you did: ${h.explanation}`).join("\n\n");
    const response = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "low" },
      system: SYSTEM + "\n\n" + (ctx.about || ""),
      tools: [tool(ctx)],
      tool_choice: { type: "auto" },
      messages: [{
        role: "user",
        content: `${describe(ctx)}\n\n${before ? before + "\n\n" : ""}The request: ${text}\n\nCall set_font with the changes.`,
      }],
    });
    if (response.stop_reason === "refusal") throw new Error("Claude לא הסכים לבקשה הזו.");
    const call = response.content.find((b) => b.type === "tool_use" && b.name === "set_font");
    if (!call) {
      const said = response.content.filter((b) => b.type === "text").map((b) => b.text).join(" ").trim();
      return { settings: [], letters: [], explanation: said || "לא היה מה לשנות." };
    }
    return check(call.input, ctx);
  }

  // The answer, kept to the settings there are and to their ranges.
  function check(input, ctx) {
    const out = { settings: [], letters: [], explanation: String((input && input.explanation) || "") };
    for (const s of (input && input.settings) || []) {
      const k = ctx.keys.find((x) => x.key === s.key);
      if (k && isFinite(s.value)) out.settings.push({ key: k.key, value: clamp(s.value, k.min, k.max) });
    }
    if (ctx.letterKeys) {
      for (const s of (input && input.letters) || []) {
        const k = ctx.letterKeys.find((x) => x.key === s.key);
        if (k && /^[א-ת]$/.test(s.letter) && isFinite(s.value)) out.letters.push({ letter: s.letter, key: k.key, value: clamp(s.value, k.min, k.max) });
      }
    }
    return out;
  }

  FontMaker.AI = { simple, ask, MODEL };
})();
