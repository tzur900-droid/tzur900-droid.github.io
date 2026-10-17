package il.avner.ozer

import android.Manifest
import android.app.SearchManager
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.provider.AlarmClock
import android.provider.CalendarContract
import android.provider.ContactsContract
import android.provider.MediaStore
import android.provider.Settings
import androidx.core.content.ContextCompat
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/** נזרק כשצריך הרשאה מהמשתמש לפני שאפשר לבצע את הפקודה. */
class NeedPermission(val permission: String) : Exception()

data class Contact(val name: String, val number: String)

class Assistant(private val ctx: Context) {

    /** נקבע כשהמשתמש סירב להרשאת חיוג ישיר. אז פותחים את החייגן בלבד. */
    var skipDirectCall = false

    private val heLocale = Locale("he", "IL")

    private val numWords: Map<String, Int> = mapOf(
        "אפס" to 0, "אחד" to 1, "אחת" to 1, "שניים" to 2, "שתיים" to 2, "שתים" to 2,
        "שני" to 2, "שתי" to 2, "שלוש" to 3, "שלושה" to 3, "ארבע" to 4, "ארבעה" to 4,
        "חמש" to 5, "חמישה" to 5, "שש" to 6, "שישה" to 6, "שבע" to 7, "שבעה" to 7,
        "שמונה" to 8, "תשע" to 9, "תשעה" to 9, "עשר" to 10, "עשרה" to 10,
        "עשרים" to 20, "שלושים" to 30, "ארבעים" to 40, "חמישים" to 50, "שישים" to 60,
        "שבעים" to 70, "שמונים" to 80, "תשעים" to 90, "מאה" to 100
    )

    private val unitMap: Map<String, Int> = mapOf(
        "שעה" to 3600, "שעות" to 3600,
        "דקה" to 60, "דקות" to 60,
        "שנייה" to 1, "שניה" to 1, "שניות" to 1
    )

    private val appAliases: Map<String, String> = mapOf(
        "וואטסאפ" to "com.whatsapp",
        "ווטסאפ" to "com.whatsapp",
        "וואצאפ" to "com.whatsapp",
        "יוטיוב" to "com.google.android.youtube",
        "מפות" to "com.google.android.apps.maps",
        "וויז" to "com.waze",
        "אינסטגרם" to "com.instagram.android",
        "פייסבוק" to "com.facebook.katana",
        "טלגרם" to "org.telegram.messenger",
        "נטפליקס" to "com.netflix.mediaclient",
        "ספוטיפיי" to "com.spotify.music",
        "גלריה" to "com.sec.android.gallery3d",
        "שעון" to "com.sec.android.app.clockpackage",
        "מחשבון" to "com.sec.android.app.popupcalculator",
        "יומן" to "com.samsung.android.calendar",
        "כרום" to "com.android.chrome",
        "גימייל" to "com.google.android.gm",
        "טיקטוק" to "com.zhiliaoapp.musically",
        "פליי סטור" to "com.android.vending",
        "אנשי קשר" to "com.samsung.android.contacts",
        "טלפון" to "com.samsung.android.dialer",
        "הודעות" to "com.samsung.android.messaging",
        "הגדרות" to "com.android.settings"
    )

    private val jokes = listOf(
        "למה המחשב הלך לרופא? כי היה לו וירוס.",
        "מה אומר ים אחד לים השני? כלום, הוא סתם נופף.",
        "למה הספר היה עצוב? כי היו לו הרבה בעיות."
    )

    private val calcRegex =
        Regex("(\\d+(?:\\.\\d+)?)\\s*(ועוד|פלוס|\\+|פחות|-|כפול|פעמים|x|\\*|חלקי|/)\\s*(\\d+(?:\\.\\d+)?)")

    private fun String.hasAny(vararg keys: String): Boolean = keys.any { this.contains(it) }

    fun handle(raw: String): String {
        val t = normalize(raw)
        if (t.isBlank()) return "לא שמעתי. נסה שוב."
        val tokens = t.split(" ").filter { it.isNotBlank() }

        return when {
            t.hasAny("פנס", "פלאש") &&
                t.hasAny("הדלק", "תדליק", "הפעל", "תפעיל", "פתח", "כבה", "תכבה", "סגור") ->
                torch(t.hasAny("כבה", "תכבה", "סגור"))

            t.hasAny("סוללה", "אחוזי טעינה") -> battery()

            t.hasAny("עוצמה", "עוצמת", "ווליום", "הקול", "הווליום") &&
                t.hasAny("הגבר", "תגביר", "הרם", "תרים", "הנמך", "תנמיך", "הורד", "תוריד", "השתק", "תשתיק") ->
                volume(t)

            t.hasAny("מה השעה", "כמה השעה", "מה הזמן") -> timeNow()

            t.hasAny("מה התאריך", "איזה יום", "איזה תאריך", "מה היום") -> dateToday()

            t.hasAny("טיימר", "סטופר") -> timer(tokens, "טיימר")

            t.contains("תזכיר לי") && t.contains("בעוד") && parseDuration(tokens) > 0 ->
                timer(tokens, t.substringAfter("תזכיר לי").trim())

            t.hasAny("שעון מעורר", "תעיר אותי", "תעירי אותי", "מעורר") -> alarm(tokens, t)

            t.hasAny("וואטסאפ", "ווטסאפ", "וואצאפ", "whatsapp") &&
                t.hasAny("שלח", "תשלח", "הודעה", "כתוב", "תכתוב", "תקשר") -> whatsapp(tokens)

            t.hasAny("שלח הודעה", "תשלח הודעה", "שלח סמס", "תשלח סמס", "שלח מסרון") -> sms(tokens)

            t.hasAny("תקשר", "חייג", "חיוג") -> call(tokens)

            t.hasAny("נווט", "ניווט") ||
                (t.contains("איך") && t.hasAny("מגיעים", "מגיע", "להגיע")) -> navigate(tokens)

            t.contains("תזכיר לי") || t.hasAny("הוסף ליומן", "תוסיף ליומן") ||
                (t.hasAny("קבע", "תקבע") && t.hasAny("פגישה", "אירוע", "תור", "יומן")) ->
                calendar(tokens, t)

            t.hasAny("נגן", "תנגן", "השמע", "תשמיע") -> music(tokens)

            t.hasAny("מצלמה", "תצלם", "סלפי") -> camera()

            t.hasAny("וויפיי", "ווי פיי", "וייפיי", "wifi") ->
                settingsScreen(Settings.ACTION_WIFI_SETTINGS, "הגדרות ה-WiFi")

            t.hasAny("בלוטוס", "בלוטות", "bluetooth") ->
                settingsScreen(Settings.ACTION_BLUETOOTH_SETTINGS, "הגדרות הבלוטוס")

            t.hasAny("מזג אוויר", "מזג האוויר", "תחזית") -> searchReply(t)

            t.hasAny("חפש", "חיפוש", "בגוגל") -> searchCmd(tokens)

            t.hasAny("פתח", "תפתח", "הפעל", "תפעיל", "היכנס") -> openApp(tokens)

            calcRegex.containsMatchIn(t) -> calc(t)

            t.hasAny("מי אתה", "מה שמך", "איך קוראים לך") -> "אני העוזר הקולי שלך."

            t.contains("בדיחה") -> jokes.random()

            t.contains("תודה") -> "בשמחה!"

            t.hasAny("מה נשמע", "שלום", "בוקר טוב", "ערב טוב") || tokens.contains("היי") ->
                "שלום! במה אפשר לעזור?"

            t.hasAny("עזרה", "מה אתה יודע", "מה אתה יכול") -> help()

            else -> searchReply(raw)
        }
    }

    // ---------- טקסט ועזרים ----------

    private fun normalize(s: String): String =
        s.lowercase(Locale.ROOT)
            .replace(Regex("[\"'״׳]"), "")
            .replace("־", " ")
            .replace(Regex("[,!?؟]"), " ")
            .replace(Regex("\\.(?!\\d)"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    private fun launch(i: Intent): Boolean {
        return try {
            ctx.startActivity(i)
            true
        } catch (e: ActivityNotFoundException) {
            false
        } catch (e: SecurityException) {
            false
        }
    }

    private fun afterKey(tokens: List<String>, keys: List<String>): List<String> {
        val idx = tokens.indexOfFirst { tok -> keys.any { k -> tok.contains(k) } }
        return if (idx < 0) emptyList() else tokens.drop(idx + 1)
    }

    private fun tokenNumber(tok: String): Int? {
        if (tok.isEmpty()) return null
        val direct = tok.toIntOrNull()
        if (direct != null) return direct
        val word = numWords[tok]
        if (word != null) return word
        if (tok.length > 1 && (tok[0] == 'ו' || tok[0] == 'ל' || tok[0] == 'ב')) {
            val s = tok.substring(1)
            val d2 = s.toIntOrNull()
            if (d2 != null) return d2
            val w2 = numWords[s]
            if (w2 != null) return w2
        }
        return null
    }

    private fun strip1(tok: String): String =
        if (tok.length > 1 && (tok[0] == 'ו' || tok[0] == 'ל' || tok[0] == 'ב')) tok.substring(1) else tok

    private fun unitSeconds(tok: String): Int {
        val a = unitMap[tok]
        if (a != null) return a
        val b = unitMap[strip1(tok)]
        return b ?: 0
    }

    private fun numberBefore(tokens: List<String>, idx: Int): Int? {
        var i = idx - 1
        var sum = 0
        var found = false
        while (i >= 0) {
            val n = tokenNumber(tokens[i]) ?: break
            sum += n
            found = true
            i--
        }
        return if (found) sum else null
    }

    private fun parseDuration(tokens: List<String>): Int {
        var total = 0.0
        for (i in tokens.indices) {
            val tok = tokens[i]
            if (strip1(tok) == "שעתיים" || tok == "שעתיים") {
                total += 7200.0
                continue
            }
            val unit = unitSeconds(tok)
            if (unit == 0) continue
            val prev = if (i > 0) strip1(tokens[i - 1]) else ""
            val n: Double = when (prev) {
                "חצי" -> 0.5
                "רבע" -> 0.25
                else -> (numberBefore(tokens, i) ?: 1).toDouble()
            }
            total += n * unit
            val next = if (i + 1 < tokens.size) strip1(tokens[i + 1]) else ""
            if (next == "חצי" && prev != "חצי") total += 0.5 * unit
        }
        return total.toInt()
    }

    private fun describeDuration(secs: Int): String {
        val h = secs / 3600
        val m = (secs % 3600) / 60
        val s = secs % 60
        val parts = ArrayList<String>()
        if (h > 0) parts.add(if (h == 1) "שעה" else "$h שעות")
        if (m > 0) parts.add(if (m == 1) "דקה" else "$m דקות")
        if (s > 0) parts.add(if (s == 1) "שנייה" else "$s שניות")
        return parts.joinToString(" ו")
    }

    /** מחזיר שעה ודקות (שעון 24 שעות) או null. */
    private fun parseClock(tokens: List<String>, t: String): Pair<Int, Int>? {
        var h: Int? = null
        var m = 0

        val colon = Regex("(\\d{1,2})[:.](\\d{2})").find(t)
        if (colon != null) {
            h = colon.groupValues[1].toInt()
            m = colon.groupValues[2].toInt()
        } else {
            var i = 0
            while (i < tokens.size && h == null) {
                if (i > 0 && tokens[i - 1] == "יום") {
                    i++
                    continue
                }
                val tok = tokens[i].removePrefix("ב").removePrefix("ל").removePrefix("-")
                val first = tokenNumber(tok)
                if (first != null && first in 0..24) {
                    var hour = first
                    var j = i + 1
                    if (j < tokens.size && (tokens[j] == "עשרה" || tokens[j] == "עשר") && hour in 1..9) {
                        hour += 10
                        j++
                    }
                    var mins = 0
                    if (j < tokens.size) {
                        val nx = tokens[j]
                        if (nx == "וחצי" || nx == "חצי") {
                            mins = 30
                        } else if (nx == "ורבע" || nx == "רבע") {
                            mins = 15
                        } else {
                            var k = j
                            while (k < tokens.size && tokens[k].startsWith("ו")) {
                                val mm = tokenNumber(tokens[k]) ?: break
                                mins += mm
                                k++
                            }
                        }
                    }
                    if (hour in 0..24 && mins in 0..59) {
                        h = hour
                        m = mins
                    }
                }
                i++
            }
        }

        if (h == null) return null
        var hh: Int = h
        val pm = t.hasAny("בערב", "אחר הצהריים", "אחרי הצהריים", "בצהריים", "אחהצ")
        if (pm && hh < 12) {
            hh += 12
        } else if (t.contains("בלילה")) {
            if (hh == 12) hh = 0 else if (hh in 6..11) hh += 12
        } else if (t.contains("בבוקר") && hh == 12) {
            hh = 0
        }
        return Pair(hh % 24, m.coerceIn(0, 59))
    }

    // ---------- פקודות ----------

    private fun timeNow(): String =
        "השעה עכשיו " + SimpleDateFormat("HH:mm", heLocale).format(Date()) + "."

    private fun dateToday(): String =
        "היום " + SimpleDateFormat("EEEE, d 'ב'MMMM yyyy", heLocale).format(Date()) + "."

    private fun battery(): String {
        val bm = ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        return "הסוללה על $level אחוז."
    }

    private fun volume(t: String): String {
        val up = t.hasAny("הגבר", "תגביר", "הרם", "תרים")
        val mute = t.hasAny("השתק", "תשתיק")
        val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val dir = when {
            mute -> AudioManager.ADJUST_MUTE
            up -> AudioManager.ADJUST_RAISE
            else -> AudioManager.ADJUST_LOWER
        }
        repeat(if (mute) 1 else 2) {
            am.adjustStreamVolume(AudioManager.STREAM_MUSIC, dir, AudioManager.FLAG_SHOW_UI)
        }
        return if (mute) "השתקתי." else if (up) "הגברתי את העוצמה." else "הנמכתי את העוצמה."
    }

    private fun torch(off: Boolean): String {
        val cm = ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        return try {
            val id = cm.cameraIdList.firstOrNull { cid ->
                val ch = cm.getCameraCharacteristics(cid)
                ch.get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true &&
                    ch.get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
            }
            if (id == null) {
                "לא מצאתי פנס במכשיר."
            } else {
                cm.setTorchMode(id, !off)
                if (off) "כיביתי את הפנס." else "הדלקתי את הפנס."
            }
        } catch (e: Exception) {
            "לא הצלחתי לשלוט בפנס."
        }
    }

    private fun timer(tokens: List<String>, label: String): String {
        val secs = parseDuration(tokens)
        if (secs <= 0) return "לכמה זמן להגדיר את הטיימר?"
        val i = Intent(AlarmClock.ACTION_SET_TIMER)
            .putExtra(AlarmClock.EXTRA_LENGTH, secs)
            .putExtra(AlarmClock.EXTRA_MESSAGE, label)
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        return if (launch(i)) {
            "הגדרתי טיימר ל" + describeDuration(secs) + "."
        } else {
            "לא מצאתי אפליקציית שעון להגדרת טיימר."
        }
    }

    private fun alarm(tokens: List<String>, t: String): String {
        if (t.contains("בעוד")) return timer(tokens, "שעון מעורר")
        val clock = parseClock(tokens, t) ?: return "לאיזו שעה להעיר אותך?"
        val i = Intent(AlarmClock.ACTION_SET_ALARM)
            .putExtra(AlarmClock.EXTRA_HOUR, clock.first)
            .putExtra(AlarmClock.EXTRA_MINUTES, clock.second)
            .putExtra(AlarmClock.EXTRA_MESSAGE, "עוזר קולי")
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        val hhmm = String.format(Locale.US, "%02d:%02d", clock.first, clock.second)
        return if (launch(i)) {
            "הגדרתי שעון מעורר ל-" + hhmm + "."
        } else {
            "לא מצאתי אפליקציית שעון."
        }
    }

    // ---------- אנשי קשר ----------

    private fun findContact(name: String): Contact? {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            throw NeedPermission(Manifest.permission.READ_CONTACTS)
        }
        val cols = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        var best: Contact? = null
        val cursor = ctx.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            cols,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?",
            arrayOf("%" + name + "%"),
            null
        )
        cursor?.use { c ->
            while (c.moveToNext()) {
                val n = c.getString(0) ?: continue
                val num = c.getString(1) ?: continue
                val current = best
                if (current == null || n.length < current.name.length) {
                    best = Contact(n, num)
                }
            }
        }
        return best
    }

    /** מחפש איש קשר מתוך 1 עד 3 המילים הראשונות. מחזיר גם כמה מילים נצרכו. */
    private fun resolveContact(tokens: List<String>): Pair<Contact, Int>? {
        if (tokens.isEmpty()) return null
        val maxN = minOf(3, tokens.size)
        for (n in maxN downTo 1) {
            val name = tokens.take(n).joinToString(" ")
            val cands = listOf(name, name.removePrefix("ל")).distinct().filter { it.length >= 2 }
            for (c in cands) {
                val found = findContact(c)
                if (found != null) return Pair(found, n)
            }
        }
        return null
    }

    private fun trimFiller(l: List<String>): List<String> {
        val filler = setOf(
            "תכתוב", "כתוב", "ותכתוב", "ותגיד", "תגיד", "שאני", "ש", "תוכן", "ואמור",
            "תאמר", "ותאמר", "בהודעה", "הודעה", "שכתוב"
        )
        return l.dropWhile { it in filler }
    }

    private fun intlNumber(n: String): String {
        val d = n.filter { it.isDigit() || it == '+' }
        return when {
            d.startsWith("+") -> d.substring(1)
            d.startsWith("00") -> d.substring(2)
            d.startsWith("0") -> "972" + d.substring(1)
            else -> d
        }
    }

    private fun call(tokens: List<String>): String {
        val rest = afterKey(tokens, listOf("תקשר", "חייג", "חיוג")).filter { it != "אל" && it != "שלי" }
        if (rest.isEmpty()) return "למי להתקשר?"

        val joined = rest.joinToString("")
        val digitCount = joined.count { it.isDigit() }
        val number: String
        val label: String
        if (digitCount >= 7) {
            number = joined.filter { it.isDigit() || it == '+' }
            label = number
        } else {
            val found = resolveContact(rest)
                ?: return "לא מצאתי איש קשר בשם " + rest.joinToString(" ") + "."
            number = found.first.number
            label = found.first.name
        }

        val uri = Uri.fromParts("tel", number, null)
        val granted = ContextCompat.checkSelfPermission(ctx, Manifest.permission.CALL_PHONE) ==
            PackageManager.PERMISSION_GRANTED
        if (!granted && !skipDirectCall) throw NeedPermission(Manifest.permission.CALL_PHONE)
        val action = if (granted) Intent.ACTION_CALL else Intent.ACTION_DIAL
        return if (launch(Intent(action, uri))) {
            "מתקשר ל" + label + "."
        } else {
            "לא הצלחתי לבצע שיחה."
        }
    }

    private fun sms(tokens: List<String>): String {
        val rest = afterKey(tokens, listOf("הודעה", "סמס", "מסרון"))
        val found = resolveContact(rest) ?: return "למי לשלוח את ההודעה?"
        val body = trimFiller(rest.drop(found.second)).joinToString(" ")
        val i = Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", found.first.number, null))
        i.putExtra("sms_body", body)
        return if (launch(i)) {
            "פותח הודעה ל" + found.first.name + ". לחץ על שלח כדי לשלוח."
        } else {
            "לא מצאתי אפליקציית הודעות."
        }
    }

    private fun whatsapp(tokens: List<String>): String {
        val dropSet = setOf(
            "שלח", "תשלח", "הודעה", "בהודעה", "ב", "את", "ל", "אל", "לי", "כתוב", "תכתוב",
            "תתקשר", "התקשר"
        )
        val cleaned = tokens.filter { tk ->
            !(tk.contains("טסאפ") || tk.contains("וואצאפ") || tk.contains("whatsapp") || tk in dropSet)
        }
        val found = resolveContact(cleaned) ?: return "למי לשלוח בוואטסאפ?"
        val body = trimFiller(cleaned.drop(found.second)).joinToString(" ")
        var url = "https://wa.me/" + intlNumber(found.first.number)
        if (body.isNotBlank()) url += "?text=" + Uri.encode(body)
        return if (launch(Intent(Intent.ACTION_VIEW, Uri.parse(url)))) {
            "פותח וואטסאפ ל" + found.first.name + ". לחץ על שלח בתוך וואטסאפ."
        } else {
            "לא הצלחתי לפתוח את וואטסאפ."
        }
    }

    // ---------- ניווט, יומן, מוזיקה ----------

    private fun navigate(tokens: List<String>): String {
        var rest = afterKey(tokens, listOf("נווט", "ניווט", "מגיעים", "מגיע", "להגיע"))
        rest = rest.dropWhile { it == "אל" || it == "ל" || it == "לכיוון" }
        if (rest.isEmpty()) return "לאן לנווט?"
        var dest = rest.joinToString(" ")
        if (dest.startsWith("ל") && dest.length > 2) dest = dest.substring(1)
        val nav = Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=" + Uri.encode(dest)))
        if (launch(nav)) return "מנווט ל" + dest + "."
        val geo = Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(dest)))
        return if (launch(geo)) "מחפש " + dest + " במפה." else "לא מצאתי אפליקציית ניווט."
    }

    private fun calendar(tokens: List<String>, t: String): String {
        val skip = setOf(
            "מחר", "מחרתיים", "היום", "ב", "בבוקר", "בערב", "בלילה", "בצהריים", "לי", "את",
            "ליומן", "ביומן", "הוסף", "תוסיף", "קבע", "תקבע", "תזכיר"
        )
        val clockRegex = Regex("\\d{1,2}([:.]\\d{2})?")
        val rest = afterKey(tokens, listOf("תזכיר", "פגישה", "אירוע", "תור", "ליומן", "ביומן"))
        val kept = rest.filter { tk ->
            tk !in skip && !clockRegex.matches(tk) && !(tk.startsWith("ב") && tokenNumber(tk) != null)
        }
        var title = kept.joinToString(" ")
        if (t.contains("פגישה")) title = ("פגישה " + title).trim()
        if (title.isBlank()) title = "אירוע"

        val cal = Calendar.getInstance()
        if (t.contains("מחרתיים")) {
            cal.add(Calendar.DAY_OF_YEAR, 2)
        } else if (t.contains("מחר")) {
            cal.add(Calendar.DAY_OF_YEAR, 1)
        }
        val clock = parseClock(tokens, t)
        if (clock != null) {
            cal.set(Calendar.HOUR_OF_DAY, clock.first)
            cal.set(Calendar.MINUTE, clock.second)
        } else {
            cal.add(Calendar.HOUR_OF_DAY, 1)
            cal.set(Calendar.MINUTE, 0)
        }
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)

        val i = Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE, title)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, cal.timeInMillis)
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, cal.timeInMillis + 3600000L)
        return if (launch(i)) {
            "פותח אירוע ביומן: " + title + ". לחץ על שמור כדי לאשר."
        } else {
            "לא מצאתי אפליקציית יומן."
        }
    }

    private fun music(tokens: List<String>): String {
        val q = afterKey(tokens, listOf("נגן", "תנגן", "השמע", "תשמיע"))
            .filter { it != "לי" && it != "את" }
            .joinToString(" ")
        if (q.isBlank()) return "איזה שיר לנגן?"
        val i = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH)
            .putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
            .putExtra(SearchManager.QUERY, q)
        if (launch(i)) return "מנגן " + q + "."
        val yt = Intent(
            Intent.ACTION_VIEW,
            Uri.parse("https://www.youtube.com/results?search_query=" + Uri.encode(q))
        )
        return if (launch(yt)) "פותח חיפוש ביוטיוב: " + q + "." else "לא מצאתי אפליקציית מוזיקה."
    }

    private fun camera(): String =
        if (launch(Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA))) {
            "פותח את המצלמה."
        } else {
            "לא מצאתי אפליקציית מצלמה."
        }

    private fun settingsScreen(action: String, label: String): String =
        if (launch(Intent(action))) {
            "פותח את " + label + ". אנדרואיד לא מאפשר לאפליקציה להדליק או לכבות את זה בעצמה."
        } else {
            "לא הצלחתי לפתוח את ההגדרות."
        }

    // ---------- חיפוש ואפליקציות ----------

    private fun webSearch(q: String): Boolean {
        val i = Intent(Intent.ACTION_WEB_SEARCH).putExtra(SearchManager.QUERY, q)
        if (launch(i)) return true
        return launch(
            Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com/search?q=" + Uri.encode(q)))
        )
    }

    private fun searchReply(q: String): String =
        if (webSearch(q)) "מחפש: " + q else "לא מצאתי דפדפן לחיפוש."

    private fun searchCmd(tokens: List<String>): String {
        val q = afterKey(tokens, listOf("חפש", "חיפוש", "בגוגל"))
            .dropWhile { it == "בגוגל" || it == "לי" || it == "את" || it == "על" }
            .joinToString(" ")
        return if (q.isBlank()) "מה לחפש?" else searchReply(q)
    }

    private fun openApp(tokens: List<String>): String {
        val skip = setOf("את", "לי", "אפליקציית", "אפליקציה", "האפליקציה")
        val name = afterKey(tokens, listOf("פתח", "פעיל", "הפעל", "היכנס"))
            .filter { it !in skip }
            .joinToString(" ")
        if (name.isBlank()) return "איזו אפליקציה לפתוח?"

        val pm = ctx.packageManager
        for ((key, pkg) in appAliases) {
            if (name.contains(key)) {
                val li = pm.getLaunchIntentForPackage(pkg)
                if (li != null && launch(li)) return "פותח " + name + "."
            }
        }

        val main = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = pm.queryIntentActivities(main, 0)
        val lower = name.lowercase(Locale.ROOT)
        val hit = apps.firstOrNull { ri ->
            val lbl = ri.loadLabel(pm).toString().lowercase(Locale.ROOT)
            lbl == lower || lbl.contains(lower) || (lbl.length >= 3 && lower.contains(lbl))
        }
        if (hit != null) {
            val li = pm.getLaunchIntentForPackage(hit.activityInfo.packageName)
            if (li != null && launch(li)) return "פותח " + name + "."
        }
        return "לא מצאתי אפליקציה בשם " + name + "."
    }

    // ---------- שונות ----------

    private fun calc(t: String): String {
        val m = calcRegex.find(t) ?: return "לא הבנתי את החישוב."
        val a = m.groupValues[1].toDouble()
        val b = m.groupValues[3].toDouble()
        val result: Double = when (m.groupValues[2]) {
            "ועוד", "פלוס", "+" -> a + b
            "פחות", "-" -> a - b
            "כפול", "פעמים", "x", "*" -> a * b
            else -> {
                if (b == 0.0) return "אי אפשר לחלק באפס."
                a / b
            }
        }
        val text = if (result == Math.floor(result) && Math.abs(result) < 1.0E15) {
            result.toLong().toString()
        } else {
            String.format(Locale.US, "%.2f", result)
        }
        return "התוצאה היא " + text + "."
    }

    private fun help(): String =
        "אני יודע: להגיד שעה ותאריך, להגדיר טיימר ושעון מעורר, להתקשר לאנשי קשר, " +
            "לשלוח הודעה ווואטסאפ, לנווט, להוסיף אירוע ליומן, לנגן מוזיקה, " +
            "להדליק פנס, לשנות עוצמה, לפתוח אפליקציות, לחפש בגוגל ולחשב."
}
