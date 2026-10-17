package il.avner.ozer

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.view.Gravity
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import java.util.Locale

class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    private lateinit var chat: LinearLayout
    private lateinit var scroll: ScrollView
    private lateinit var status: TextView
    private lateinit var input: EditText
    private lateinit var mic: ImageButton
    private lateinit var autoListen: CheckBox
    private lateinit var assistant: Assistant

    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var listening = false
    private var requestedPermission: String? = null
    private var pendingCommand: String? = null
    private val handler = Handler(Looper.getMainLooper())

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val perm = requestedPermission
            requestedPermission = null
            if (perm == Manifest.permission.RECORD_AUDIO) {
                if (granted) {
                    startListening()
                } else {
                    setStatus("אין הרשאה למיקרופון. אפשר להקליד פקודה.")
                }
            } else {
                val cmd = pendingCommand
                pendingCommand = null
                if (perm == Manifest.permission.CALL_PHONE) {
                    if (!granted) assistant.skipDirectCall = true
                    if (cmd != null) process(cmd, false)
                } else if (granted && cmd != null) {
                    process(cmd, false)
                } else {
                    say("בלי ההרשאה לא אוכל לבצע את זה.")
                }
            }
        }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {}

        override fun onBeginningOfSpeech() {
            setStatus("שומע...")
        }

        override fun onRmsChanged(rmsdB: Float) {}

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            setStatus("מעבד...")
        }

        override fun onError(error: Int) {
            listening = false
            updateMic()
            val msg = when (error) {
                SpeechRecognizer.ERROR_NO_MATCH,
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "לא שמעתי. לחץ על המיקרופון ונסה שוב."
                SpeechRecognizer.ERROR_NETWORK,
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "אין חיבור לאינטרנט לזיהוי הדיבור."
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "אין הרשאה למיקרופון."
                SpeechRecognizer.ERROR_CLIENT -> "לחץ על המיקרופון כדי לדבר."
                12, 13 -> "זיהוי דיבור בעברית לא זמין. בדוק בהגדרות Google שהעברית מותקנת."
                else -> "שגיאת זיהוי דיבור ($error)."
            }
            setStatus(msg)
        }

        override fun onResults(results: Bundle?) {
            listening = false
            updateMic()
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
            if (text.isNullOrBlank()) {
                setStatus("לא שמעתי. נסה שוב.")
                return
            }
            setStatus("")
            process(text, true)
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val p = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
            if (!p.isNullOrBlank()) setStatus(p)
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        chat = findViewById(R.id.chat)
        scroll = findViewById(R.id.scroll)
        status = findViewById(R.id.status)
        input = findViewById(R.id.input)
        mic = findViewById(R.id.mic)
        autoListen = findViewById(R.id.autoListen)

        assistant = Assistant(this)
        tts = TextToSpeech(this, this)

        val prefs = getSharedPreferences("ozer", MODE_PRIVATE)
        autoListen.isChecked = prefs.getBoolean("auto", true)
        autoListen.setOnCheckedChangeListener { _, checked ->
            prefs.edit().putBoolean("auto", checked).apply()
        }

        mic.setOnClickListener {
            if (listening) stopListening() else startListening()
        }
        findViewById<Button>(R.id.sendBtn).setOnClickListener { submitTyped() }
        input.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                submitTyped()
                true
            } else {
                false
            }
        }

        addBubble(
            "שלום! אני העוזר הקולי שלך. אפשר להגיד למשל: מה השעה, טיימר לחמש דקות, " +
                "התקשר לאמא, נווט לתל אביב, תעיר אותי בשבע וחצי, פתח יוטיוב, " +
                "שלח הודעה לדני אני מאחר. כדי לראות הכול, תגיד: עזרה.",
            false
        )

        if (autoListen.isChecked) {
            handler.postDelayed({ startListening() }, 400)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (autoListen.isChecked) startListening()
    }

    override fun onInit(statusCode: Int) {
        if (statusCode != TextToSpeech.SUCCESS) {
            setStatus("הקראה בקול לא זמינה. התשובות יוצגו על המסך.")
            return
        }
        val r = tts?.setLanguage(Locale("he", "IL"))
        ttsReady = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
        if (!ttsReady) {
            setStatus("אין קול בעברית. הגדרות ← ניהול כללי ← המרת טקסט לדיבור.")
        }
    }

    private fun startListening() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            askPermission(Manifest.permission.RECORD_AUDIO)
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            setStatus("זיהוי דיבור לא זמין במכשיר. אפשר להקליד פקודה.")
            return
        }
        tts?.stop()
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(this)
            recognizer?.setRecognitionListener(listener)
        }
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "he-IL")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "he-IL")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        listening = true
        updateMic()
        setStatus("מקשיב...")
        recognizer?.startListening(i)
    }

    private fun stopListening() {
        recognizer?.cancel()
        listening = false
        updateMic()
        setStatus("לחץ על המיקרופון ודבר")
    }

    private fun askPermission(permission: String) {
        requestedPermission = permission
        permissionLauncher.launch(permission)
    }

    private fun submitTyped() {
        val text = input.text.toString().trim()
        if (text.isNotEmpty()) {
            input.setText("")
            process(text, true)
        }
    }

    private fun process(text: String, echo: Boolean) {
        if (echo) addBubble(text, true)
        try {
            say(assistant.handle(text))
        } catch (e: NeedPermission) {
            pendingCommand = text
            askPermission(e.permission)
        }
    }

    private fun say(text: String) {
        if (text.isBlank()) return
        addBubble(text, false)
        if (ttsReady) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "ozer")
        }
    }

    private fun setStatus(text: String) {
        status.text = text
    }

    private fun updateMic() {
        mic.setBackgroundResource(if (listening) R.drawable.bg_mic_active else R.drawable.bg_mic)
        mic.setPadding(dp(20), dp(20), dp(20), dp(20))
    }

    private fun addBubble(text: String, fromUser: Boolean) {
        val tv = TextView(this)
        tv.text = text
        tv.textSize = 17f
        tv.setPadding(dp(14), dp(10), dp(14), dp(10))
        tv.maxWidth = (resources.displayMetrics.widthPixels * 0.8f).toInt()
        tv.setBackgroundResource(if (fromUser) R.drawable.bubble_user else R.drawable.bubble_bot)
        tv.setTextColor(
            ContextCompat.getColor(
                this,
                if (fromUser) R.color.bubble_user_text else R.color.bubble_bot_text
            )
        )
        val lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        )
        lp.topMargin = dp(8)
        lp.gravity = if (fromUser) Gravity.START else Gravity.END
        chat.addView(tv, lp)
        scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        recognizer?.destroy()
        recognizer = null
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }
}
