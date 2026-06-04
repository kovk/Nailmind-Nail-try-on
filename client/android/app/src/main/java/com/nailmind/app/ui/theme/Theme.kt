package com.nailmind.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp

private val LightColors = lightColorScheme(
    primary = RoseAccent,
    secondary = DeepPlum,
    tertiary = RoseAccent,
    background = Cloud,
    surface = androidx.compose.ui.graphics.Color.White,
    surfaceVariant = RoseTint,
    onPrimary = androidx.compose.ui.graphics.Color.White,
    onBackground = Ink,
    onSurface = Ink,
    outline = SoftLine
)

private val DarkColors = darkColorScheme(
    primary = RoseAccentDark,
    secondary = RoseAccent,
    tertiary = RoseAccentDark,
    background = NightSurface,
    surface = DeepPlum,
    surfaceVariant = androidx.compose.ui.graphics.Color(0xFF2A1F27),
    onPrimary = Ink,
    onBackground = androidx.compose.ui.graphics.Color(0xFFF8EEF2),
    onSurface = androidx.compose.ui.graphics.Color(0xFFF8EEF2),
    outline = androidx.compose.ui.graphics.Color(0xFF59404F)
)

private val NailShapes = Shapes(
    extraSmall = androidx.compose.foundation.shape.RoundedCornerShape(10.dp),
    small = androidx.compose.foundation.shape.RoundedCornerShape(14.dp),
    medium = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
    large = androidx.compose.foundation.shape.RoundedCornerShape(24.dp),
    extraLarge = androidx.compose.foundation.shape.RoundedCornerShape(28.dp)
)

@Composable
fun NailMindTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        shapes = NailShapes,
        content = content
    )
}
