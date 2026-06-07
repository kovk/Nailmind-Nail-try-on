package com.nailmind.app.data.api

import com.nailmind.app.data.config.AppConfig

data class AuthRequest(
    val email: String,
    val password: String
)

data class RegisterRequest(
    val name: String,
    val email: String,
    val password: String
)

data class AuthUserDto(
    val name: String,
    val email: String,
    val preferences: List<String> = emptyList()
)

data class AuthResponse(
    val token: String,
    val user: AuthUserDto
)

data class AuthMeResponse(
    val user: AuthUserDto
)

data class StatusResponse(
    val status: String
)

data class TrackEventRequest(
    val eventName: String,
    val deviceId: String? = null,
    val styleId: String? = null,
    val storeId: String? = null,
    val sourcePage: String? = null,
    val sourceChannel: String? = null,
    val sessionId: String? = null,
    val payload: Map<String, @JvmSuppressWildcards Any>? = null,
    val occurredAt: String? = null
)

data class TrackEventResponse(
    val eventId: String
)

data class HomeResponse(
    val hotKeywords: List<String>,
    val recommended: List<StyleDto>,
    val hot: List<StyleDto>
)

data class StyleDto(
    val id: String,
    val name: String,
    val vibe: String,
    val price: String,
    val nailType: String,
    val skinTone: String,
    val tags: List<String>,
    val colors: List<String>,
    val imageUrl: String? = null,
    val tryOnStyleId: Int? = null
)

data class StylesResponse(
    val items: List<StyleDto>
)

data class SearchResponse(
    val query: String,
    val items: List<StyleDto>
)

data class StyleDetailResponse(
    val style: StyleDto,
    val userCases: String,
    val canFavorite: Boolean,
    val canTryOn: Boolean,
    val favorited: Boolean
)

data class FavoriteToggleResponse(
    val styleId: String,
    val favorited: Boolean
)

data class TryOnUploadResponse(
    val hand_id: String,
    val image_url: String? = null,
    val db_id: Int,
    val message: String? = null
)

data class LegacyTryOnUploadResponse(
    val objectKey: String,
    val fileName: String? = null
)

data class HandImageDto(
    val id: String,
    val dbId: Int,
    val imageUrl: String,
    val sourceType: String,
    val skinTone: String,
    val handType: String
)

data class HandImagesResponse(
    val hands: List<HandImageDto>,
    val total: Int
)

data class SyncTryOnRequest(
    val handId: String? = null,
    val handImageId: Int? = null,
    val styleId: Int,
    val selectedLength: String = "natural_short",
    val selectedShape: String = "squoval"
)

data class SyncTryOnResponse(
    val result_url: String,
    val duration_ms: Int,
    val style_name: String,
    val source: String
)

data class TryOnHistoryItemDto(
    val id: String,
    val jobId: String? = null,
    val resultUrl: String,
    val durationMs: Int,
    val styleName: String,
    val styleId: String,
    val source: String,
    val selectedLength: String,
    val selectedShape: String,
    val createdAt: String
)

fun StyleDto.normalized(): StyleDto = copy(imageUrl = AppConfig.normalizeMediaUrl(imageUrl))

fun HandImageDto.normalized(): HandImageDto = copy(imageUrl = AppConfig.normalizeMediaUrl(imageUrl).orEmpty())

fun SyncTryOnResponse.normalized(): SyncTryOnResponse = copy(result_url = AppConfig.normalizeMediaUrl(result_url).orEmpty())

fun TryOnHistoryItemDto.normalized(): TryOnHistoryItemDto = copy(
    resultUrl = AppConfig.normalizeTryOnPreviewUrl(resultUrl, jobId).orEmpty()
)

data class TryOnHistoryResponse(
    val items: List<TryOnHistoryItemDto>,
    val total: Int
)

data class CreateTryOnJobRequest(
    val styleId: String,
    val sourceImageKey: String? = null,
    val selectedLength: String = "natural_short",
    val selectedShape: String = "squoval"
)

data class RerenderTryOnJobRequest(
    val selectedLength: String? = null,
    val selectedShape: String? = null
)

data class TryOnJobsResponse(
    val items: List<TryOnJobDto>
)

data class TryOnJobDto(
    val id: String,
    val userId: String,
    val styleId: String,
    val styleName: String,
    val sourceImageKey: String,
    val status: String,
    val stage: String,
    val progress: Int,
    val selectedLength: String,
    val selectedShape: String,
    val resultImageKey: String? = null,
    val detectedTraits: Map<String, String>? = null,
    val errorCode: String? = null,
    val errorMessage: String? = null,
    val createdAt: String,
    val updatedAt: String,
    val completedAt: String? = null,
    val resultImageUrl: String? = null
)

fun TryOnJobDto.normalized(): TryOnJobDto = copy(
    resultImageUrl = AppConfig.normalizeMediaUrl(resultImageUrl)
)

data class StoreDto(
    val id: String,
    val name: String,
    val distance: String,
    val priceBand: String,
    val score: String,
    val slots: List<String>,
    val openHours: String,
    val artists: Int,
    val works: String
)

data class StoresResponse(
    val items: List<StoreDto>
)

data class StoreSlotsResponse(
    val storeId: String,
    val slots: List<String>
)

data class BookingRequest(
    val storeId: String,
    val styleId: String,
    val slot: String,
    val name: String,
    val phone: String,
    val note: String = ""
)

data class BookingsResponse(
    val items: List<BookingDto>
)

data class BookingDto(
    val id: String,
    val status: String,
    val storeId: String,
    val storeName: String,
    val styleId: String,
    val styleName: String,
    val slot: String,
    val price: String,
    val name: String,
    val phone: String,
    val note: String,
    val createdAt: String,
    val confirmedAt: String? = null
)

data class ProfileResponse(
    val profile: AuthUserDto,
    val favoritesCount: Int,
    val bookingCount: Int,
    val tryOnCount: Int
)

data class SettingsResponse(
    val stylePreferences: String,
    val notifications: String,
    val privacy: String
)
