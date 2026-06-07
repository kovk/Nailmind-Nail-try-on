package com.nailmind.app.data.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import com.nailmind.app.data.config.AppConfig

class NailMindRepository(
    private val service: NailMindApiService = NailMindApiClient.service
) {
    suspend fun register(name: String, email: String, password: String): AuthResponse =
        service.register(RegisterRequest(name = name, email = email, password = password))

    suspend fun login(email: String, password: String): AuthResponse =
        service.login(AuthRequest(email = email, password = password))

    suspend fun authMe(): AuthMeResponse = service.authMe()

    suspend fun logout(): StatusResponse = service.logout()

    suspend fun trackEvent(
        eventName: String,
        deviceId: String,
        sessionId: String,
        styleId: String? = null,
        storeId: String? = null,
        sourcePage: String? = null,
        sourceChannel: String? = null,
        payload: Map<String, Any>? = null
    ): TrackEventResponse = service.trackEvent(
        TrackEventRequest(
            eventName = eventName,
            deviceId = deviceId,
            styleId = styleId,
            storeId = storeId,
            sourcePage = sourcePage,
            sourceChannel = sourceChannel,
            sessionId = sessionId,
            payload = payload
        )
    )

    suspend fun home(): HomeResponse = service.home().let { response ->
        response.copy(
            recommended = response.recommended.map { it.normalized() },
            hot = response.hot.map { it.normalized() },
        )
    }

    suspend fun styles(tag: String? = null): StylesResponse = service.styles(tag).let { response ->
        response.copy(items = response.items.map { it.normalized() })
    }

    suspend fun searchStyles(query: String): SearchResponse = service.searchStyles(query).let { response ->
        response.copy(items = response.items.map { it.normalized() })
    }

    suspend fun styleDetail(styleId: String): StyleDetailResponse = service.styleDetail(styleId).let { response ->
        response.copy(style = response.style.normalized())
    }

    suspend fun favorites(): StylesResponse = service.favorites().let { response ->
        response.copy(items = response.items.map { it.normalized() })
    }

    suspend fun setFavorite(styleId: String, favorited: Boolean): FavoriteToggleResponse {
        return if (favorited) service.addFavorite(styleId) else service.removeFavorite(styleId)
    }

    suspend fun uploadHandImage(file: File): TryOnUploadResponse {
        val requestBody = file.asRequestBody("image/*".toMediaType())
        val part = MultipartBody.Part.createFormData("file", file.name, requestBody)
        return service.uploadHandImage(part)
    }

    suspend fun handImages(): HandImagesResponse = service.handImages().let { response ->
        response.copy(hands = response.hands.map { it.normalized() })
    }

    suspend fun syncTryOn(
        handId: String? = null,
        handImageId: Int? = null,
        styleId: Int,
        selectedLength: String,
        selectedShape: String
    ): SyncTryOnResponse = service.syncTryOn(
        SyncTryOnRequest(
            handId = handId,
            handImageId = handImageId,
            styleId = styleId,
            selectedLength = selectedLength,
            selectedShape = selectedShape
        )
    ).normalized()

    suspend fun tryOnHistory(): TryOnHistoryResponse = service.tryOnHistory().let { response ->
        response.copy(items = response.items.map { it.normalized() })
    }

    suspend fun resultImageBytesByUrl(url: String): ByteArray {
        val response = service.resultImageByUrl(AppConfig.normalizeMediaUrl(url) ?: url)
        if (!response.isSuccessful) {
            error("加载试戴结果失败: HTTP ${response.code()}")
        }
        return response.body()?.bytes() ?: error("试戴结果为空")
    }

    suspend fun uploadAsyncTryOnImage(file: File): LegacyTryOnUploadResponse {
        val requestBody = file.asRequestBody("image/*".toMediaType())
        val part = MultipartBody.Part.createFormData("file", file.name, requestBody)
        return service.uploadTryOnImage(part)
    }

    suspend fun tryOnJobs(): TryOnJobsResponse = service.tryOnJobs().let { response ->
        response.copy(items = response.items.map { it.normalized() })
    }

    suspend fun createTryOnJob(
        styleId: String,
        sourceImageKey: String?,
        selectedLength: String,
        selectedShape: String
    ): TryOnJobDto = service.createTryOnJob(
        CreateTryOnJobRequest(
            styleId = styleId,
            sourceImageKey = sourceImageKey,
            selectedLength = selectedLength,
            selectedShape = selectedShape
        )
    ).normalized()

    suspend fun tryOnJob(jobId: String): TryOnJobDto = service.tryOnJob(jobId).normalized()

    suspend fun tryOnResult(jobId: String): TryOnJobDto = service.tryOnResult(jobId).normalized()

    suspend fun rerenderTryOn(jobId: String, selectedLength: String?, selectedShape: String?): TryOnJobDto =
        service.rerenderTryOn(
            jobId,
            RerenderTryOnJobRequest(selectedLength = selectedLength, selectedShape = selectedShape)
        ).normalized()

    suspend fun tryOnResultImageBytes(jobId: String): ByteArray {
        val response = service.resultImage(jobId)
        if (!response.isSuccessful) {
            error("加载试戴结果失败: HTTP ${response.code()}")
        }
        return response.body()?.bytes() ?: error("试戴结果为空")
    }

    suspend fun stores(): StoresResponse = service.stores()

    suspend fun storeDetail(storeId: String): StoreDto = service.storeDetail(storeId)

    suspend fun storeSlots(storeId: String): StoreSlotsResponse = service.storeSlots(storeId)

    suspend fun bookings(): BookingsResponse = service.bookings()

    suspend fun createBooking(
        storeId: String,
        styleId: String,
        slot: String,
        name: String,
        phone: String,
        note: String
    ): BookingDto = service.createBooking(
        BookingRequest(
            storeId = storeId,
            styleId = styleId,
            slot = slot,
            name = name,
            phone = phone,
            note = note
        )
    )

    suspend fun booking(bookingId: String): BookingDto = service.booking(bookingId)

    suspend fun confirmBooking(bookingId: String): BookingDto = service.confirmBooking(bookingId)

    suspend fun profile(): ProfileResponse = service.profile()

    suspend fun settings(): SettingsResponse = service.settings()
}
