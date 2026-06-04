package com.nailmind.app.data.config

import com.nailmind.app.BuildConfig

object AppConfig {
    const val authTokenPreference = "auth_token"
    const val preferencesName = "nailmind_prefs"
    const val deviceIdPreference = "device_id"
    const val sessionIdPreference = "session_id"

    val apiBaseUrl: String = BuildConfig.API_BASE_URL.ensureTrailingSlash()
    val mediaBaseUrl: String = BuildConfig.API_MEDIA_BASE_URL.ensureTrailingSlash()
    val apiTimeoutSeconds: Long = BuildConfig.API_TIMEOUT_SECONDS
}

private fun String.ensureTrailingSlash(): String = if (endsWith("/")) this else "$this/"
