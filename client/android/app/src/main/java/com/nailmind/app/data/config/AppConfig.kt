package com.nailmind.app.data.config

import com.nailmind.app.BuildConfig
import java.net.URI

object AppConfig {
    const val authTokenPreference = "auth_token"
    const val preferencesName = "nailmind_prefs"
    const val deviceIdPreference = "device_id"
    const val sessionIdPreference = "session_id"
    const val pendingTryOnJobPreference = "pending_try_on_job"
    const val pendingTryOnStylePreference = "pending_try_on_style"

    val apiBaseUrl: String = BuildConfig.API_BASE_URL.ensureTrailingSlash()
    val mediaBaseUrl: String = BuildConfig.API_MEDIA_BASE_URL.ensureTrailingSlash()
    val apiTimeoutSeconds: Long = BuildConfig.API_TIMEOUT_SECONDS

    fun normalizeMediaUrl(rawUrl: String?): String? {
        if (rawUrl.isNullOrBlank()) return null
        if (rawUrl.startsWith("/")) {
            return mediaBaseUrl.trimEnd('/') + rawUrl
        }
        return runCatching {
            val uri = URI(rawUrl)
            val host = uri.host?.lowercase().orEmpty()
            if (host == "localhost" || host == "127.0.0.1" || host == "0.0.0.0") {
                val mediaUri = URI(mediaBaseUrl)
                URI(
                    mediaUri.scheme,
                    mediaUri.userInfo,
                    mediaUri.host,
                    mediaUri.port,
                    uri.path,
                    uri.query,
                    uri.fragment,
                ).toString()
            } else {
                rawUrl
            }
        }.getOrElse { rawUrl }
    }

    fun normalizeTryOnPreviewUrl(rawUrl: String?, jobId: String?): String? {
        val normalized = normalizeMediaUrl(rawUrl)
        if (normalized.isNullOrBlank()) return null
        val safeJobId = jobId?.takeIf { it.isNotBlank() } ?: return normalized
        return if (normalized.contains("/api/try-on/jobs/") && normalized.endsWith("/result-image")) {
            mediaBaseUrl.trimEnd('/') + "/files/results/$safeJobId.png"
        } else {
            normalized
        }
    }
}

private fun String.ensureTrailingSlash(): String = if (endsWith("/")) this else "$this/"
