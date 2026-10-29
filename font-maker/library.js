// The fonts you may start from. Every one has a free license that allows changing it:
// OFL (SIL Open Font License) or GPL (the Culmus fonts, with the font exception). A changed font
// gets a new name and keeps the license and the names of the original designers.
(function () {
  "use strict";

  const OFL = "OFL", GPL = "GPL";
  const f = (id, name, file, license, licenseFile, group, about) => ({ id, name, file, license, licenseFile, group, about });

  FontMaker.library = [
    f("frankruhl", "פרנק-רוהל ליברה", "FrankRuhlLibre-Regular.ttf", OFL, "OFL-FrankRuhlLibre.txt", "ספר", "האות הקלאסית של ספרי קודש ועיתונים"),
    f("davidlibre", "דוד ליברה", "DavidLibre-Regular.ttf", OFL, "OFL-DavidLibre.txt", "ספר", "אות ספר רחבה ונוחה לקריאה"),
    f("notoserif", "נוטו סריף", "NotoSerifHebrew-Regular.ttf", OFL, "OFL-NotoHebrew.txt", "ספר", "אות ספר מודרנית, עם ניקוד וטעמים"),
    f("bellefair", "בלפייר", "Bellefair-Regular.ttf", OFL, "OFL-bellefair.txt", "ספר", "אלגנטית ועדינה, לכותרות"),
    f("frankruehlclm", "פרנק-רוהל CLM", "FrankRuehlCLM-Medium.otf", GPL, "LICENSE-Culmus.txt", "ספר", "פרנק-רוהל של קולמוס"),
    f("davidclm", "דוד CLM", "DavidCLM-Medium.otf", GPL, "LICENSE-Culmus.txt", "ספר", "דוד של קולמוס"),
    f("drugulin", "דרוגולין", "DrugulinCLM-Bold.otf", GPL, "LICENSE-Culmus.txt", "ספר", "אות דפוס ישנה ומודגשת"),
    f("keter", "כתר", "KeterYG-Medium.ttf", GPL, "LICENSE-Culmus.txt", "ספר", "בהשראת כתר ארם צובא"),
    f("shofar", "שופר", "ShofarRegular.ttf", GPL, "LICENSE-Culmus.txt", "ספר", "אות ספר רכה"),

    f("heebo", "חיבו", "Heebo.ttf", OFL, "OFL-heebo.txt", "נקי", "נקייה ומודרנית, הכי נפוצה באתרים"),
    f("assistant", "אסיסטנט", "Assistant.ttf", OFL, "OFL-assistant.txt", "נקי", "נקייה וצרה"),
    f("rubik", "רוביק", "Rubik.ttf", OFL, "OFL-rubik.txt", "נקי", "פינות מעט עגולות, ידידותית"),
    f("alef", "אלף", "Alef-Regular.ttf", OFL, "OFL-alef.txt", "נקי", "פשוטה ונעימה, גם לטקסט"),
    f("notosans", "נוטו סאנס", "NotoSansHebrew.ttf", OFL, "OFL-notosanshebrew.txt", "נקי", "נקייה, עם ניקוד מלא"),
    f("plex", "IBM פלקס", "IBMPlexSansHebrew-Regular.ttf", OFL, "OFL-ibmplexsanshebrew.txt", "נקי", "טכנולוגית ומסודרת"),
    f("miriamlibre", "מרים ליברה", "MiriamLibre.ttf", OFL, "OFL-miriamlibre.txt", "נקי", "מרים בעיצוב חדש"),
    f("miriam", "מרים CLM", "MiriamCLM-Book.otf", GPL, "LICENSE-Culmus.txt", "נקי", "מרים הקלאסית"),
    f("nachlieli", "נחליאלי", "NachlieliCLM-Light.otf", GPL, "LICENSE-Culmus.txt", "נקי", "כמו Arial עברי"),
    f("aharoni", "אהרוני", "AharoniCLM-Book.otf", GPL, "LICENSE-Culmus.txt", "נקי", "גאומטרית ומרובעת"),
    f("varela", "ורלה עגול", "VarelaRound-Regular.ttf", OFL, "OFL-varelaround.txt", "נקי", "עגולה ורכה"),
    f("fredoka", "פרדוקה", "Fredoka.ttf", OFL, "OFL-fredoka.txt", "נקי", "עגולה ושמחה, לילדים"),

    f("secular", "סקולר", "SecularOne-Regular.ttf", OFL, "OFL-secularone.txt", "כותרת", "עבה ובולטת"),
    f("suez", "סואץ", "SuezOne-Regular.ttf", OFL, "OFL-suezone.txt", "כותרת", "עבה עם תגים"),
    f("karantina", "קרנטינה", "Karantina-Regular.ttf", OFL, "OFL-karantina.txt", "כותרת", "צרה וגבוהה"),
    f("amatic", "אמטיק", "AmaticSC-Regular.ttf", OFL, "OFL-amaticsc.txt", "כותרת", "כמו כתיבה בטוש"),

    f("rashi", "נוטו רש״י", "NotoRashiHebrew-Regular.ttf", OFL, "OFL-NotoHebrew.txt", "כתב", "כתב רש״י של פירושים"),
    f("playpen", "פלייפן", "PlaypenSansHebrew.ttf", OFL, "OFL-playpensanshebrew.txt", "כתב", "כמו כתב יד של ילד"),
    f("solitreo", "סוליטריאו", "Solitreo-Regular.ttf", OFL, "OFL-solitreo.txt", "כתב", "כתב יד ספרדי ישן"),
    f("stamash", "סת״ם אשכנזי", "StamAshkenazCLM.ttf", GPL, "LICENSE-Culmus.txt", "כתב", "כמו בספר תורה, אשכנזי"),
    f("stamsef", "סת״ם ספרדי", "StamSefaradCLM.ttf", GPL, "LICENSE-Culmus.txt", "כתב", "כמו בספר תורה, ספרדי"),
  ];

  // Where the files are: next to the page, or inside it (the one-file version of the program).
  FontMaker.libraryFile = async function (name) {
    const inside = FontMaker.libraryData && FontMaker.libraryData[name];
    if (inside) {
      const bin = atob(inside);
      const out = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out.buffer;
    }
    const r = await fetch("fonts/" + name);
    if (!r.ok) throw new Error("לא נמצא הקובץ " + name);
    return r.arrayBuffer();
  };
})();
