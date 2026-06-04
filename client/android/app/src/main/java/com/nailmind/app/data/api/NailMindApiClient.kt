package com.nailmind.app.data.api

import com.nailmind.app.data.config.AppConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object NailMindApiClient {
    @Volatile
    private var authTokenProvider: (() -> String?)? = null

    fun setAuthTokenProvider(provider: () -> String?) {
        authTokenProvider = provider
    }

    val service: NailMindApiService by lazy {
        Retrofit.Builder()
            .baseUrl(AppConfig.apiBaseUrl)
            .client(buildHttpClient())
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(NailMindApiService::class.java)
    }

    private fun buildHttpClient(): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        val auth = Interceptor { chain ->
            val builder = chain.request().newBuilder()
            authTokenProvider?.invoke()?.takeIf { it.isNotBlank() }?.let {
                builder.header("Authorization", "Bearer $it")
            }
            chain.proceed(builder.build())
        }
        return OkHttpClient.Builder()
            .addInterceptor(auth)
            .addInterceptor(logging)
            .connectTimeout(AppConfig.apiTimeoutSeconds, TimeUnit.SECONDS)
            .readTimeout(AppConfig.apiTimeoutSeconds, TimeUnit.SECONDS)
            .writeTimeout(AppConfig.apiTimeoutSeconds, TimeUnit.SECONDS)
            .build()
    }
}
