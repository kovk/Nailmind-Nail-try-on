package com.nailmind.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.nailmind.app.ui.NailMindApp
import com.nailmind.app.ui.theme.NailMindTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            NailMindTheme {
                NailMindApp()
            }
        }
    }
}
