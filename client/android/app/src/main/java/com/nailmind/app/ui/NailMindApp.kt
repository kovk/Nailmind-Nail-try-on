package com.nailmind.app.ui

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ContentValues
import android.content.Intent
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ExperimentalAnimationApi
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.BookmarkBorder
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.FavoriteBorder
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.NotificationsNone
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.PhotoCamera
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material.icons.rounded.Storefront
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import coil.compose.AsyncImagePainter
import coil.compose.SubcomposeAsyncImage
import coil.compose.SubcomposeAsyncImageContent
import com.nailmind.app.data.api.AuthResponse
import com.nailmind.app.data.api.AuthUserDto
import com.nailmind.app.data.api.BookingDto
import com.nailmind.app.data.api.HomeResponse
import com.nailmind.app.data.api.NailMindApiClient
import com.nailmind.app.data.api.NailMindRepository
import com.nailmind.app.data.api.SettingsResponse
import com.nailmind.app.data.api.StoreDto
import com.nailmind.app.data.api.StyleDto
import com.nailmind.app.data.api.TryOnHistoryItemDto
import com.nailmind.app.data.config.AppConfig
import com.nailmind.app.ui.theme.RoseAccent
import com.nailmind.app.ui.theme.RoseTint
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.UUID
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private enum class MainTab(
    val title: String,
    val icon: ImageVector
) {
    Home("首页", Icons.Rounded.Home),
    Styles("款式", Icons.Rounded.GridView),
    TryOn("AI试戴", Icons.Rounded.AutoAwesome),
    Booking("预约", Icons.Rounded.CalendarMonth),
    Profile("我的", Icons.Rounded.Person)
}

private sealed interface Screen {
    data object Login : Screen
    data object Register : Screen
    data class Tab(val tab: MainTab) : Screen
    data class StyleDetail(val styleId: String) : Screen
    data object Search : Screen
    data class SearchResult(val query: String) : Screen
    data object Ranking : Screen
    data class TryOnUpload(val styleId: String, val fromFavorites: Boolean = false) : Screen
    data class TryOnProcessing(val styleId: String, val jobId: String) : Screen
    data class TryOnResult(val styleId: String, val jobId: String) : Screen
    data object TryOnHistory : Screen
    data object DiyDesigner : Screen
    data object Favorites : Screen
    data object BookingRecords : Screen
    data class StoreDetail(val storeId: String, val styleId: String? = null) : Screen
    data class BookingForm(val storeId: String, val styleId: String) : Screen
    data class BookingConfirm(val bookingId: String) : Screen
    data class BookingSuccess(val bookingId: String) : Screen
    data object Settings : Screen
}

private data class AuthUser(
    val name: String,
    val email: String,
    val preferences: List<String> = emptyList()
)

private data class NailStyle(
    val id: String,
    val name: String,
    val vibe: String,
    val price: String,
    val nailType: String,
    val skinTone: String,
    val colors: List<Color>,
    val tags: List<String>,
    val imageUrl: String? = null,
    val tryOnStyleId: Int? = null
)

private enum class StyleBrowseTab(val title: String) {
    NailShape("甲型"),
    Effect("效果"),
    Vibe("风格")
}

private data class StyleBrowseOption(
    val label: String,
    val keywords: List<String>
)

private val nailShapeBrowseOptions = listOf(
    StyleBrowseOption("小短梯", listOf("小短梯", "短梯", "短方", "方圆")),
    StyleBrowseOption("短方圆", listOf("短方圆", "短椭圆", "椭圆", "裸", "优雅")),
    StyleBrowseOption("中方", listOf("中方", "方形", "经典", "红")),
    StyleBrowseOption("中椭圆", listOf("中椭圆", "椭圆", "玫瑰", "粉")),
    StyleBrowseOption("中短梯", listOf("中短梯", "梯形", "莫兰迪", "雾霾")),
    StyleBrowseOption("长梯", listOf("长梯", "闪钻", "奢华", "银河")),
    StyleBrowseOption("长椭圆", listOf("长椭圆", "流星", "丝绒", "大理石")),
    StyleBrowseOption("尖水滴", listOf("尖水滴", "长方", "暗黑", "深海", "酒红"))
)

private val effectBrowseOptions = listOf(
    StyleBrowseOption("法式", listOf("法式")),
    StyleBrowseOption("渐变", listOf("渐变", "彩虹", "星空")),
    StyleBrowseOption("猫眼", listOf("猫眼", "银河", "流星")),
    StyleBrowseOption("纯色", listOf("纯色", "经典红", "奶油白", "裸色", "珍珠白")),
    StyleBrowseOption("手绘", listOf("手绘", "樱花", "花", "纹理")),
    StyleBrowseOption("镜面", listOf("镜面", "金", "香槟", "玫瑰金")),
    StyleBrowseOption("浮雕", listOf("浮雕", "大理石", "丝绒")),
    StyleBrowseOption("钻饰", listOf("钻", "闪钻", "奢华", "亮片"))
)

private val vibeBrowseOptions = listOf(
    StyleBrowseOption("韩系", listOf("韩", "奶油", "豆沙", "蜜桃", "裸")),
    StyleBrowseOption("日系", listOf("日", "樱花", "马卡龙", "薄荷")),
    StyleBrowseOption("中式", listOf("中式", "新中式", "酒红", "朱砂", "玫瑰金")),
    StyleBrowseOption("欧美", listOf("欧美", "暗黑", "深海", "经典红")),
    StyleBrowseOption("节庆", listOf("节庆", "红", "金", "彩虹", "银河")),
    StyleBrowseOption("甜美", listOf("甜美", "粉", "蜜桃", "马卡龙", "樱花")),
    StyleBrowseOption("日常", listOf("日常", "裸", "奶油白", "珍珠白", "豆沙")),
    StyleBrowseOption("酷感", listOf("酷", "暗黑", "深海", "雾霾蓝")),
    StyleBrowseOption("极繁", listOf("极繁", "闪钻", "奢华", "大理石", "流星"))
)

private data class Store(
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

private data class BookingRecord(
    val id: String,
    val status: String,
    val storeName: String,
    val styleName: String,
    val slot: String
)

private data class UserSettings(
    val stylePreferences: String,
    val notifications: String,
    val privacy: String
)

private data class TryOnStatus(
    val jobId: String = "",
    val styleId: String = "",
    val styleName: String = "",
    val stage: String = "",
    val progress: Int = 0,
    val status: String = "",
    val errorMessage: String? = null
)

private const val tryOnNotificationChannelId = "tryon_updates"

private fun ensureTryOnNotificationChannel(context: Context) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
    val manager = context.getSystemService(NotificationManager::class.java) ?: return
    val channel = NotificationChannel(
        tryOnNotificationChannelId,
        "试戴提醒",
        NotificationManager.IMPORTANCE_DEFAULT
    ).apply {
        description = "用于提醒试戴结果已生成"
    }
    manager.createNotificationChannel(channel)
}

private fun canPostNotifications(context: Context): Boolean {
    return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
}

private fun showTryOnReadyNotification(context: Context, styleName: String) {
    ensureTryOnNotificationChannel(context)
    if (!canPostNotifications(context)) return
    val notification = NotificationCompat.Builder(context, tryOnNotificationChannelId)
        .setSmallIcon(android.R.drawable.ic_dialog_info)
        .setContentTitle("试戴已完成")
        .setContentText("$styleName 已生成效果图，可前往“我的 - 试戴记录”查看")
        .setPriority(NotificationCompat.PRIORITY_DEFAULT)
        .setAutoCancel(true)
        .build()
    NotificationManagerCompat.from(context).notify(styleName.hashCode(), notification)
}

private val styles: List<NailStyle> = emptyList()
private val stores: List<Store> = emptyList()
private val defaultHotKeywords: List<String> = emptyList()

private fun StyleDto.toUi(): NailStyle = NailStyle(
    id = id,
    name = name,
    vibe = vibe,
    price = price,
    nailType = nailType,
    skinTone = skinTone,
    colors = colors.map { Color(android.graphics.Color.parseColor(it)) },
    tags = tags,
    imageUrl = imageUrl,
    tryOnStyleId = tryOnStyleId
)

private fun StoreDto.toUi(): Store = Store(
    id = id,
    name = name,
    distance = distance,
    priceBand = priceBand,
    score = score,
    slots = slots,
    openHours = openHours,
    artists = artists,
    works = works
)

private fun AuthUserDto.toUi(): AuthUser = AuthUser(name = name, email = email, preferences = preferences)

private fun BookingDto.toUi(): BookingRecord = BookingRecord(
    id = id,
    status = status,
    storeName = storeName,
    styleName = styleName,
    slot = slot
)

private fun buildDisplayedTryOnHistory(
    items: List<TryOnHistoryItemDto>,
    status: TryOnStatus
): List<TryOnHistoryItemDto> {
    val merged = items.toMutableList()
    val shouldShowPending = status.jobId.isNotBlank() &&
        status.styleId.isNotBlank() &&
        status.status in setOf("queued", "processing")
    if (shouldShowPending && merged.none { it.jobId == status.jobId }) {
        merged.add(
            0,
            TryOnHistoryItemDto(
                id = "pending-${status.jobId}",
                jobId = status.jobId,
                resultUrl = "",
                durationMs = 0,
                styleName = status.styleName.ifBlank { "试戴处理中" },
                styleId = status.styleId,
                source = "pending",
                selectedLength = "",
                selectedShape = "",
                createdAt = java.time.Instant.now().toString()
            )
        )
    }
    return merged.sortedByDescending { it.createdAt }.distinctBy { it.styleId }
}

private fun SettingsResponse.toUi(): UserSettings = UserSettings(
    stylePreferences = stylePreferences,
    notifications = notifications,
    privacy = privacy
)

private fun selectedLengthToApi(value: String): String = when (value) {
    "自然短甲" -> "natural_short"
    "中短" -> "medium_short"
    "修长" -> "elongated"
    else -> "natural_short"
}

private fun selectedShapeToApi(value: String): String = when (value) {
    "方圆" -> "squoval"
    "椭圆" -> "oval"
    "杏仁" -> "almond"
    else -> "squoval"
}

private fun saveBitmapToCache(context: Context, bitmap: Bitmap): File {
    val file = File(context.cacheDir, "nailmind-hand-${System.currentTimeMillis()}.png")
    FileOutputStream(file).use { output ->
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
    }
    return file
}

private fun copyUriToCache(context: Context, uri: Uri): File? {
    val input = context.contentResolver.openInputStream(uri) ?: return null
    val file = File(context.cacheDir, "nailmind-hand-${System.currentTimeMillis()}.jpg")
    input.use { stream ->
        FileOutputStream(file).use { output -> stream.copyTo(output) }
    }
    return file
}

private fun saveBitmapToGallery(context: Context, bitmap: Bitmap, styleName: String): Result<Unit> {
    return runCatching {
        val resolver = context.contentResolver
        val displayName = "nailmind-${styleName.takeIf { it.isNotBlank() } ?: "tryon"}-${System.currentTimeMillis()}.png"
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, displayName)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Images.Media.RELATIVE_PATH, "${Environment.DIRECTORY_PICTURES}/NailMind")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
        }
        val collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val uri = resolver.insert(collection, values) ?: throw IOException("无法创建图片保存记录")
        try {
            resolver.openOutputStream(uri)?.use { output ->
                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) {
                    throw IOException("图片写入失败")
                }
            } ?: throw IOException("无法打开图片输出流")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                values.clear()
                values.put(MediaStore.Images.Media.IS_PENDING, 0)
                resolver.update(uri, values, null, null)
            }
        } catch (error: Exception) {
            resolver.delete(uri, null, null)
            throw error
        }
    }
}

private fun galleryPermission(): String = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
    Manifest.permission.READ_MEDIA_IMAGES
} else {
    Manifest.permission.READ_EXTERNAL_STORAGE
}

private fun stageLabel(stage: String): String = when (stage) {
    "queued" -> "排队中"
    "preparing" -> "准备任务"
    "loading_image" -> "加载手部照片"
    "vision_pipeline" -> "识别手部与甲床"
    "rendering" -> "渲染试戴效果"
    "completed" -> "已完成"
    "failed" -> "处理失败"
    else -> stage.ifBlank { "排队中" }
}

@OptIn(ExperimentalAnimationApi::class, ExperimentalMaterial3Api::class)
@Composable
fun NailMindApp() {
    val context = LocalContext.current
    val sharedPreferences = remember(context) {
        context.getSharedPreferences(AppConfig.preferencesName, Context.MODE_PRIVATE)
    }
    val deviceId = remember {
        sharedPreferences.getString(AppConfig.deviceIdPreference, null)
            ?: UUID.randomUUID().toString().also {
                sharedPreferences.edit().putString(AppConfig.deviceIdPreference, it).apply()
            }
    }
    val sessionId = remember {
        UUID.randomUUID().toString().also {
            sharedPreferences.edit().putString(AppConfig.sessionIdPreference, it).apply()
        }
    }
    val repository = remember { NailMindRepository() }
    val coroutineScope = rememberCoroutineScope()
    var currentTab by remember { mutableStateOf(MainTab.Home) }
    val stack = remember {
        mutableStateListOf<Screen>(
            if (sharedPreferences.getString(AppConfig.authTokenPreference, null).isNullOrBlank()) Screen.Login else Screen.Tab(MainTab.Home)
        )
    }
    val favorites = remember { mutableStateListOf<String>() }
    var selectedLength by remember { mutableStateOf("自然短甲") }
    var selectedShape by remember { mutableStateOf("方圆") }
    var selectedStoreId by remember { mutableStateOf("") }
    var authUser by remember { mutableStateOf<AuthUser?>(null) }
    var authToken by remember { mutableStateOf(sharedPreferences.getString(AppConfig.authTokenPreference, null)) }
    var authLoading by remember { mutableStateOf(false) }
    var authError by remember { mutableStateOf<String?>(null) }
    var styleItems by remember { mutableStateOf(styles) }
    var homeRecommended by remember { mutableStateOf(styles.take(2)) }
    var homeHot by remember { mutableStateOf(styles) }
    var hotKeywords by remember { mutableStateOf(defaultHotKeywords) }
    var storeItems by remember { mutableStateOf(stores) }
    var bookingRecords by remember { mutableStateOf(emptyList<BookingRecord>()) }
    var pendingBooking by remember { mutableStateOf<BookingDto?>(null) }
    var userSettings by remember { mutableStateOf(UserSettings("", "", "")) }
    var searchResults by remember { mutableStateOf(styleItems) }
    var tryOnStatus by remember { mutableStateOf(TryOnStatus()) }
    var tryOnHistoryItems by remember { mutableStateOf(emptyList<TryOnHistoryItemDto>()) }
    var tryOnHistoryManageMode by remember { mutableStateOf(false) }
    var latestTryOnBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var lastTryOnSourceFile by remember { mutableStateOf<File?>(null) }
    var lastTryOnHandId by remember { mutableStateOf<String?>(null) }
    var bookingSubmitting by remember { mutableStateOf(false) }
    var bookingError by remember { mutableStateOf<String?>(null) }
    var tryOnSubmitting by remember { mutableStateOf(false) }
    var tryOnError by remember { mutableStateOf<String?>(null) }
    var pageRefreshing by remember { mutableStateOf(false) }
    var tryOnPollJob by remember { mutableStateOf<Job?>(null) }
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !canPostNotifications(context)) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    fun persistPendingTryOn(jobId: String, styleId: String) {
        sharedPreferences.edit()
            .putString(AppConfig.pendingTryOnJobPreference, jobId)
            .putString(AppConfig.pendingTryOnStylePreference, styleId)
            .apply()
    }

    fun clearPendingTryOn() {
        sharedPreferences.edit()
            .remove(AppConfig.pendingTryOnJobPreference)
            .remove(AppConfig.pendingTryOnStylePreference)
            .apply()
    }

    fun resetToLogin() {
        authUser = null
        authToken = null
        authError = null
        favorites.clear()
        bookingRecords = emptyList()
        pendingBooking = null
        userSettings = UserSettings("", "", "")
        tryOnStatus = TryOnStatus()
        tryOnHistoryItems = emptyList()
        tryOnPollJob?.cancel()
        tryOnPollJob = null
        latestTryOnBitmap = null
        lastTryOnSourceFile = null
        lastTryOnHandId = null
        bookingError = null
        tryOnError = null
        sharedPreferences.edit().remove(AppConfig.authTokenPreference).apply()
        clearPendingTryOn()
        currentTab = MainTab.Home
        stack.clear()
        stack.add(Screen.Login)
    }

    fun completeAuth(response: AuthResponse) {
        authUser = response.user.toUi()
        authToken = response.token
        sharedPreferences.edit().putString(AppConfig.authTokenPreference, response.token).apply()
        currentTab = MainTab.Home
        stack.clear()
        stack.add(Screen.Tab(MainTab.Home))
    }

    fun go(screen: Screen) {
        if (screen is Screen.Tab) {
            currentTab = screen.tab
        }
        stack.add(screen)
    }

    fun trackEvent(
        eventName: String,
        styleId: String? = null,
        storeId: String? = null,
        sourcePage: String? = null,
        sourceChannel: String? = null,
        payload: Map<String, Any>? = null
    ) {
        coroutineScope.launch {
            runCatching {
                repository.trackEvent(
                    eventName = eventName,
                    deviceId = deviceId,
                    sessionId = sessionId,
                    styleId = styleId,
                    storeId = storeId,
                    sourcePage = sourcePage,
                    sourceChannel = sourceChannel,
                    payload = payload
                )
            }
        }
    }

    fun refreshTryOnHistory() {
        coroutineScope.launch {
            runCatching { repository.tryOnHistory().items }
                .onSuccess { tryOnHistoryItems = it }
        }
    }

    fun openTryOnHistoryResult(item: TryOnHistoryItemDto) {
        coroutineScope.launch {
            runCatching {
                val imageBytes = repository.resultImageBytesByUrl(item.resultUrl)
                BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
            }.onSuccess { bitmap ->
                val resultJobId = item.jobId ?: item.id
                latestTryOnBitmap = bitmap
                tryOnStatus = TryOnStatus(
                    jobId = resultJobId,
                    styleId = item.styleId,
                    styleName = item.styleName,
                    stage = item.source,
                    progress = 100,
                    status = "completed"
                )
                go(Screen.TryOnResult(item.styleId, resultJobId))
            }.onFailure { error ->
                tryOnError = error.message ?: "打开试戴记录失败"
            }
        }
    }

    fun monitorTryOnJob(styleId: String, jobId: String, navigateToProcessing: Boolean = false) {
        tryOnPollJob?.cancel()
        tryOnPollJob = coroutineScope.launch {
            if (navigateToProcessing) {
                go(Screen.TryOnProcessing(styleId, jobId))
            }
            while (isActive) {
                runCatching { repository.tryOnJob(jobId) }
                    .onSuccess { job ->
                        tryOnStatus = TryOnStatus(
                            jobId = job.id,
                            styleId = job.styleId,
                            styleName = job.styleName,
                            stage = job.stage,
                            progress = job.progress,
                            status = job.status,
                            errorMessage = job.errorMessage
                        )
                        when (job.status) {
                            "completed" -> {
                                val imageBytes = repository.tryOnResultImageBytes(jobId)
                                latestTryOnBitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
                                refreshTryOnHistory()
                                clearPendingTryOn()
                                tryOnSubmitting = false
                                val currentScreen = stack.lastOrNull()
                                val viewingJob = currentScreen == Screen.TryOnProcessing(styleId, jobId) ||
                                    currentScreen == Screen.TryOnResult(styleId, jobId)
                                if (viewingJob) {
                                    stack[stack.lastIndex] = Screen.TryOnResult(styleId, jobId)
                                } else {
                                    showTryOnReadyNotification(
                                        context,
                                        styleItems.firstOrNull { it.id == styleId }?.name ?: job.styleName
                                    )
                                }
                                return@launch
                            }

                            "failed" -> {
                                clearPendingTryOn()
                                tryOnSubmitting = false
                                tryOnError = job.errorMessage ?: "试戴生成失败，请更换更清晰的手部照片后重试"
                                return@launch
                            }
                        }
                    }
                    .onFailure { error ->
                        tryOnStatus = tryOnStatus.copy(errorMessage = error.message ?: "试戴任务状态获取失败")
                    }
                delay(2000)
            }
        }
    }

    fun launchTryOn(styleId: String, sourceFile: File, sourceChannel: String) {
        coroutineScope.launch {
            tryOnSubmitting = true
            tryOnError = null
            latestTryOnBitmap = null
            runCatching {
                lastTryOnSourceFile = sourceFile
                val upload = repository.uploadAsyncTryOnImage(sourceFile)
                repository.createTryOnJob(
                    styleId = styleId,
                    sourceImageKey = upload.objectKey,
                    selectedLength = selectedLengthToApi(selectedLength),
                    selectedShape = selectedShapeToApi(selectedShape)
                )
            }.onSuccess { job ->
                trackEvent(
                    eventName = "tryon_source_select",
                    styleId = styleId,
                    sourcePage = "tryon_upload",
                    sourceChannel = sourceChannel,
                    payload = mapOf("fileName" to sourceFile.name)
                )
                requestNotificationPermissionIfNeeded()
                persistPendingTryOn(job.id, styleId)
                tryOnStatus = TryOnStatus(
                    jobId = job.id,
                    styleId = styleId,
                    styleName = styleItems.firstOrNull { it.id == styleId }?.name.orEmpty(),
                    stage = job.stage,
                    progress = job.progress,
                    status = job.status,
                    errorMessage = job.errorMessage
                )
                tryOnSubmitting = false
                monitorTryOnJob(styleId, job.id, navigateToProcessing = true)
            }.onFailure { error ->
                tryOnError = error.message ?: "创建试戴任务失败"
                tryOnSubmitting = false
            }
        }
    }

    fun rerunTryOn(styleId: String, jobId: String) {
        coroutineScope.launch {
            tryOnSubmitting = true
            tryOnError = null
            latestTryOnBitmap = null
            runCatching {
                val canRerenderExistingJob = Regex("^tryon-\\d+$").matches(jobId) || Regex("^job-\\d+$").matches(jobId)
                if (canRerenderExistingJob) {
                    repository.rerenderTryOn(
                        jobId = jobId,
                        selectedLength = selectedLengthToApi(selectedLength),
                        selectedShape = selectedShapeToApi(selectedShape)
                    )
                } else {
                    val lastFile = lastTryOnSourceFile ?: error("缺少上一张手部照片，请重新上传")
                    val upload = repository.uploadAsyncTryOnImage(lastFile)
                    repository.createTryOnJob(
                        styleId = styleId,
                        sourceImageKey = upload.objectKey,
                        selectedLength = selectedLengthToApi(selectedLength),
                        selectedShape = selectedShapeToApi(selectedShape)
                    )
                }
            }.onSuccess { job ->
                persistPendingTryOn(job.id, styleId)
                tryOnStatus = TryOnStatus(
                    jobId = job.id,
                    styleId = styleId,
                    styleName = styleItems.firstOrNull { it.id == styleId }?.name.orEmpty(),
                    stage = job.stage,
                    progress = job.progress,
                    status = job.status,
                    errorMessage = job.errorMessage
                )
                tryOnSubmitting = false
                stack[stack.lastIndex] = Screen.TryOnProcessing(styleId, job.id)
                monitorTryOnJob(styleId, job.id)
            }.onFailure { error ->
                tryOnError = error.message ?: "重新生成试戴失败"
                tryOnSubmitting = false
            }
        }
    }

    fun back() {
        if (stack.size > 1) {
            stack.removeLast()
            val top = stack.last()
            if (top is Screen.Tab) currentTab = top.tab
        }
    }

    suspend fun bootstrapData() {
        val me = repository.authMe().user.toUi()
        val home = repository.home()
        val fetchedStyles = repository.styles().items.map { it.toUi() }.filter { !it.imageUrl.isNullOrBlank() }
        val fetchedFavorites = repository.favorites().items.map { it.id }
        val fetchedStores = repository.stores().items.map { it.toUi() }
        val fetchedBookings = repository.bookings().items.map { it.toUi() }
        val fetchedSettings = repository.settings().toUi()
        val fetchedTryOnHistory = repository.tryOnHistory().items

        authUser = me
        styleItems = fetchedStyles
        favorites.clear()
        favorites.addAll(fetchedFavorites)
        storeItems = fetchedStores
        bookingRecords = fetchedBookings
        userSettings = fetchedSettings
        tryOnHistoryItems = fetchedTryOnHistory
        hotKeywords = home.hotKeywords
        homeRecommended = home.recommended.map { it.toUi() }.filter { !it.imageUrl.isNullOrBlank() }
        homeHot = home.hot.map { it.toUi() }.filter { !it.imageUrl.isNullOrBlank() }
        searchResults = styleItems
        if (selectedStoreId !in storeItems.map { it.id }) {
            selectedStoreId = storeItems.firstOrNull()?.id.orEmpty()
        }
    }

    fun refreshPageData() {
        coroutineScope.launch {
            pageRefreshing = true
            runCatching { bootstrapData() }
                .onFailure { error ->
                    Toast.makeText(context, error.message ?: "刷新失败，请稍后再试", Toast.LENGTH_SHORT).show()
                }
            pageRefreshing = false
        }
    }

    fun toggleFavorite(styleId: String) {
        val shouldFavorite = !favorites.contains(styleId)
        coroutineScope.launch {
            runCatching { repository.setFavorite(styleId, shouldFavorite) }
                .onSuccess {
                    if (shouldFavorite) favorites.add(styleId) else favorites.remove(styleId)
                }
        }
    }

    fun openBookingForStyle(styleId: String) {
        val firstStore = storeItems.firstOrNull()
        if (firstStore == null) {
            Toast.makeText(context, "当前还没有可预约门店", Toast.LENGTH_SHORT).show()
            return
        }
        selectedStoreId = firstStore.id
        go(Screen.BookingForm(firstStore.id, styleId))
    }

    val displayedTryOnHistoryItems = buildDisplayedTryOnHistory(tryOnHistoryItems, tryOnStatus)

    fun findBooking(bookingId: String): BookingDto? {
        if (pendingBooking?.id == bookingId) return pendingBooking
        val record = bookingRecords.firstOrNull { it.id == bookingId } ?: return null
        return BookingDto(
            id = record.id,
            status = record.status,
            storeId = "",
            storeName = record.storeName,
            styleId = "",
            styleName = record.styleName,
            slot = record.slot,
            price = "",
            name = authUser?.name ?: "",
            phone = "",
            note = "",
            createdAt = "",
            confirmedAt = null
        )
    }

    LaunchedEffect(Unit) {
        NailMindApiClient.setAuthTokenProvider { authToken }
        if (!authToken.isNullOrBlank()) {
            runCatching { bootstrapData() }
                .onFailure { resetToLogin() }
        }
    }

    LaunchedEffect(authToken) {
        NailMindApiClient.setAuthTokenProvider { authToken }
        if (!authToken.isNullOrBlank()) {
            val pendingJobId = sharedPreferences.getString(AppConfig.pendingTryOnJobPreference, null)
            val pendingStyleId = sharedPreferences.getString(AppConfig.pendingTryOnStylePreference, null)
            if (!pendingJobId.isNullOrBlank() && !pendingStyleId.isNullOrBlank()) {
                monitorTryOnJob(pendingStyleId, pendingJobId)
            }
        }
    }

    val current = stack.last()
    val isAuthenticated = authToken != null
    BackHandler(enabled = stack.size > 1 && current !is Screen.Login && current !is Screen.Register) {
        back()
    }
    val showHomeChrome = current is Screen.Tab && current.tab == MainTab.Home
    val styleDetailStyle = (current as? Screen.StyleDetail)?.let { screen ->
        styleItems.firstOrNull { it.id == screen.styleId } ?: styleItems.firstOrNull()
    }
    fun shareStyle(style: NailStyle?) {
        if (style == null) return
        trackEvent(
            eventName = "style_share",
            styleId = style.id,
            sourcePage = "style_detail",
            sourceChannel = "native_share"
        )
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, style.name)
            putExtra(Intent.EXTRA_TEXT, "看看这款美甲：${style.name} ${AppConfig.apiBaseUrl}admin")
        }
        context.startActivity(Intent.createChooser(intent, "分享款式"))
    }
    val topBarTitle = when (current) {
        Screen.Login -> "登录"
        Screen.Register -> "注册"
        is Screen.Tab -> current.tab.title
        is Screen.StyleDetail -> "款式详情"
        Screen.Search -> "搜索款式"
        is Screen.SearchResult -> "搜索结果"
        Screen.Ranking -> "热门排行榜"
        is Screen.TryOnUpload -> "上传手部照片"
        is Screen.TryOnProcessing -> "手部识别中"
        is Screen.TryOnResult -> "试戴结果"
        Screen.TryOnHistory -> "试戴记录"
        Screen.DiyDesigner -> "DIY设计"
        Screen.Favorites -> "我的收藏"
        Screen.BookingRecords -> "预约记录"
        is Screen.StoreDetail -> "门店详情"
        is Screen.BookingForm -> "填写预约"
        is Screen.BookingConfirm -> "确认预约"
        is Screen.BookingSuccess -> "预约成功"
        Screen.Settings -> "设置"
    }

    Scaffold(
        topBar = {
            if (isAuthenticated && !showHomeChrome) {
                CenterAlignedTopAppBar(
                    title = { Text(topBarTitle, fontWeight = FontWeight.SemiBold) },
                    navigationIcon = {
                        if (stack.size > 1) {
                            IconButton(onClick = ::back) {
                                Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "返回")
                            }
                        }
                    },
                    actions = {
                        if (current is Screen.StyleDetail) {
                            IconButton(onClick = { shareStyle(styleDetailStyle) }) {
                                Icon(Icons.Rounded.Share, contentDescription = "分享")
                            }
                        }
                        if (current is Screen.TryOnHistory) {
                            TextButton(onClick = { tryOnHistoryManageMode = !tryOnHistoryManageMode }) {
                                Text(if (tryOnHistoryManageMode) "完成" else "管理")
                            }
                        }
                    },
                    colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background
                    )
                )
            }
        },
        bottomBar = {
            if (isAuthenticated && current is Screen.Tab) {
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shape = MaterialTheme.shapes.large,
                    shadowElevation = 8.dp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 92.dp)
                            .padding(horizontal = 8.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        MainTab.entries.forEach { tab ->
                            val selected = currentTab == tab
                            val isTryOn = tab == MainTab.TryOn
                            TextButton(
                                onClick = {
                                    currentTab = tab
                                stack.clear()
                                stack.add(Screen.Tab(tab))
                            },
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = if (isTryOn) 72.dp else 64.dp),
                            contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp)
                        ) {
                            if (isTryOn) {
                                Surface(
                                    color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
                                    shape = MaterialTheme.shapes.large,
                                        tonalElevation = 0.dp,
                                        shadowElevation = 2.dp,
                                        border = androidx.compose.foundation.BorderStroke(
                                            1.dp,
                                            MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)
                                        )
                                    ) {
                                        Column(
                                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                                            horizontalAlignment = Alignment.CenterHorizontally
                                        ) {
                                            Icon(
                                                imageVector = tab.icon,
                                                contentDescription = tab.title,
                                                tint = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.primary,
                                                modifier = Modifier.size(22.dp)
                                            )
                                            Spacer(Modifier.height(4.dp))
                                            Text(
                                                text = tab.title,
                                                color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f),
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                    }
                                } else {
                                    Surface(
                                        color = if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else Color.Transparent,
                                        shape = MaterialTheme.shapes.medium
                                    ) {
                                        Column(
                                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                                            horizontalAlignment = Alignment.CenterHorizontally
                                        ) {
                                            Icon(
                                                imageVector = tab.icon,
                                                contentDescription = tab.title,
                                                tint = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.52f)
                                            )
                                            Spacer(Modifier.height(4.dp))
                                            Text(
                                                text = tab.title,
                                                color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.62f),
                                                fontSize = 12.sp
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            } else if (isAuthenticated && current is Screen.StyleDetail && styleDetailStyle != null) {
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shadowElevation = 8.dp,
                    modifier = Modifier.navigationBarsPadding()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        OutlinedButton(
                            onClick = { toggleFavorite(styleDetailStyle.id) },
                            modifier = Modifier.weight(1f)
                        ) {
                            Text(if (favorites.contains(styleDetailStyle.id)) "已收藏" else "收藏")
                        }
                        Button(
                            onClick = { go(Screen.TryOnUpload(styleDetailStyle.id)) },
                            modifier = Modifier.weight(1.2f)
                        ) {
                            Text("AI试戴")
                        }
                        OutlinedButton(
                            onClick = { openBookingForStyle(styleDetailStyle.id) },
                            modifier = Modifier.weight(1.1f)
                        ) {
                            Text("预约同款")
                        }
                    }
                }
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        AnimatedContent(
            targetState = current,
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) { screen ->
            when (screen) {
                Screen.Login -> AuthScreen(
                    title = "欢迎回到 Nail Mind",
                    subtitle = "登录后才能使用试戴、收藏、预约和个人中心。",
                    primaryLabel = "登录",
                    secondaryLabel = "没有账号，去注册",
                    initialName = "",
                    initialEmail = "",
                    initialPassword = "",
                    showNameField = false,
                    loading = authLoading,
                    errorMessage = authError,
                    onPrimary = { _, email, password ->
                        coroutineScope.launch {
                            authLoading = true
                            authError = null
                            runCatching { repository.login(email = email, password = password) }
                                .onSuccess {
                                    completeAuth(it)
                                    runCatching { bootstrapData() }
                                        .onFailure { error -> authError = error.message ?: "初始化首页数据失败" }
                                }
                                .onFailure { error ->
                                    authError = error.message ?: "登录失败"
                                }
                            authLoading = false
                        }
                    },
                    onSecondary = {
                        stack.clear()
                        stack.add(Screen.Register)
                    }
                )

                Screen.Register -> AuthScreen(
                    title = "创建你的账号",
                    subtitle = "注册后才能保存收藏、试戴记录和预约订单。",
                    primaryLabel = "注册并进入",
                    secondaryLabel = "已有账号，去登录",
                    initialName = "",
                    initialEmail = "",
                    initialPassword = "",
                    showNameField = true,
                    loading = authLoading,
                    errorMessage = authError,
                    onPrimary = { name, email, password ->
                        coroutineScope.launch {
                            authLoading = true
                            authError = null
                            runCatching { repository.register(name = name.ifBlank { "新用户" }, email = email, password = password) }
                                .onSuccess {
                                    completeAuth(it)
                                    runCatching { bootstrapData() }
                                        .onFailure { error -> authError = error.message ?: "初始化首页数据失败" }
                                }
                                .onFailure { error ->
                                    authError = error.message ?: "注册失败"
                                }
                            authLoading = false
                        }
                    },
                    onSecondary = {
                        stack.clear()
                        stack.add(Screen.Login)
                    }
                )

                is Screen.Tab -> when (screen.tab) {
                    MainTab.Home -> HomeScreen(
                        recommended = homeRecommended,
                        hot = homeHot,
                        refreshing = pageRefreshing,
                        onRefresh = ::refreshPageData,
                        onSearch = { go(Screen.Search) },
                        onSeeMore = {
                            currentTab = MainTab.Styles
                            stack.clear()
                            stack.add(Screen.Tab(MainTab.Styles))
                        },
                        onRanking = { go(Screen.Ranking) },
                        onStyleClick = { go(Screen.StyleDetail(it)) }
                    )
                    MainTab.Styles -> StylesScreen(
                        styles = styleItems,
                        refreshing = pageRefreshing,
                        onRefresh = ::refreshPageData,
                        onStyleClick = { go(Screen.StyleDetail(it)) }
                    )
                    MainTab.TryOn -> TryOnHubScreen(
                        favorites = styleItems.filter { favorites.contains(it.id) },
                        hot = homeHot,
                        systemRecommended = homeRecommended.ifEmpty { styleItems.take(6) },
                        onHotPick = { go(Screen.TryOnUpload(it)) },
                        onFavoritePick = { go(Screen.TryOnUpload(it, fromFavorites = true)) },
                        onRecommendedPick = { go(Screen.TryOnUpload(it)) },
                        onDiy = { go(Screen.DiyDesigner) }
                    )
                    MainTab.Booking -> BookingScreen(
                        stores = storeItems,
                        onStoreClick = { go(Screen.StoreDetail(it, null)) }
                    )
                    MainTab.Profile -> ProfileScreen(
                        user = authUser ?: AuthUser("账户", ""),
                        favoritesCount = favorites.size,
                        tryOnHistoryCount = displayedTryOnHistoryItems.size,
                        onFavorites = { go(Screen.Favorites) },
                        onTryOnHistory = { go(Screen.TryOnHistory) },
                        onRecords = { go(Screen.BookingRecords) },
                        onSettings = { go(Screen.Settings) }
                    )
                }

                is Screen.StyleDetail -> {
                    val style = styleItems.firstOrNull { it.id == screen.styleId } ?: return@AnimatedContent
                    StyleDetailScreen(
                        style = style,
                        favorite = favorites.contains(style.id),
                        onToggleFavorite = { toggleFavorite(style.id) },
                        onTryOn = { go(Screen.TryOnUpload(style.id)) },
                        onBook = { openBookingForStyle(style.id) }
                    )
                }

                Screen.Search -> SearchScreen(
                    hotKeywords = hotKeywords,
                    onSearch = {
                        coroutineScope.launch {
                            searchResults = runCatching { repository.searchStyles(it).items.map { item -> item.toUi() } }
                                .getOrDefault(styleItems.filter { style -> style.name.contains(it) || style.vibe.contains(it) || style.tags.any { tag -> tag.contains(it) } })
                            go(Screen.SearchResult(it))
                        }
                    }
                )

                is Screen.SearchResult -> SearchResultScreen(
                    query = screen.query,
                    result = searchResults,
                    onStyleClick = {
                        trackEvent(
                            eventName = "search_result_click",
                            styleId = it,
                            sourcePage = "search_result",
                            payload = mapOf("query" to screen.query)
                        )
                        go(Screen.StyleDetail(it))
                    }
                )

                Screen.Ranking -> RankingScreen(
                    styles = (homeHot + homeRecommended + styleItems).distinctBy { it.id }.take(12),
                    onStyleClick = { go(Screen.StyleDetail(it)) }
                )

                Screen.DiyDesigner -> DiyDesignerScreen(
                    onSave = {
                        Toast.makeText(context, "DIY款式已保存为草稿", Toast.LENGTH_SHORT).show()
                        back()
                    },
                    onTryOn = {
                        val target = styleItems.firstOrNull()?.id
                        if (target == null) {
                            Toast.makeText(context, "暂无可试戴款式", Toast.LENGTH_SHORT).show()
                        } else {
                            go(Screen.TryOnUpload(target))
                        }
                    }
                )

                is Screen.TryOnUpload -> TryOnUploadScreen(
                    style = styleItems.firstOrNull { it.id == screen.styleId } ?: return@AnimatedContent,
                    fromFavorites = screen.fromFavorites,
                    loading = tryOnSubmitting,
                    errorMessage = tryOnError,
                    lastSourceFile = lastTryOnSourceFile,
                    onStartProcessing = { sourceFile, sourceChannel -> launchTryOn(screen.styleId, sourceFile, sourceChannel) }
                )

                is Screen.TryOnProcessing -> {
                    TryOnProcessingScreen(
                        stage = tryOnStatus.stage,
                        progress = tryOnStatus.progress,
                        errorMessage = tryOnStatus.errorMessage,
                        onDone = { go(Screen.TryOnResult(screen.styleId, screen.jobId)) },
                        onLeave = {
                            currentTab = MainTab.Home
                            stack.clear()
                            stack.add(Screen.Tab(MainTab.Home))
                        }
                    )
                }

                is Screen.TryOnResult -> TryOnResultScreen(
                    style = styleItems.firstOrNull { it.id == screen.styleId } ?: return@AnimatedContent,
                    favorite = favorites.contains(screen.styleId),
                    resultStatus = tryOnStatus.status,
                    resultBitmap = latestTryOnBitmap,
                    onOpenStyle = { go(Screen.StyleDetail(screen.styleId)) },
                    onRetake = { go(Screen.TryOnUpload(screen.styleId)) },
                    onToggleFavorite = { toggleFavorite(screen.styleId) },
                    onBook = { openBookingForStyle(screen.styleId) },
                    onSaveImage = {
                        val bitmap = latestTryOnBitmap
                        if (bitmap == null) {
                            Toast.makeText(context, "试戴图还没生成完成", Toast.LENGTH_SHORT).show()
                        } else {
                            saveBitmapToGallery(context, bitmap, styleItems.firstOrNull { it.id == screen.styleId }?.name ?: "tryon")
                                .onSuccess {
                                    Toast.makeText(context, "图片已保存到相册", Toast.LENGTH_SHORT).show()
                                }
                                .onFailure { error ->
                                    Toast.makeText(context, error.message ?: "保存失败，请稍后再试", Toast.LENGTH_SHORT).show()
                                }
                        }
                    }
                )

                Screen.TryOnHistory -> TryOnHistoryScreen(
                    items = displayedTryOnHistoryItems,
                    styles = styleItems,
                    refreshing = pageRefreshing,
                    manageMode = tryOnHistoryManageMode,
                    onRefresh = ::refreshPageData,
                    onShare = { selected ->
                        if (selected.isNotEmpty()) {
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, "我的 Nail Mind 试戴记录：${selected.joinToString("、") { it.styleName }}")
                            }
                            context.startActivity(Intent.createChooser(intent, "分享试戴记录"))
                        }
                    },
                    onMoveToFavorites = { selected ->
                        selected.map { it.styleId }.filter { it.isNotBlank() }.forEach { styleId ->
                            if (!favorites.contains(styleId)) favorites.add(styleId)
                        }
                        Toast.makeText(context, "已移入收藏", Toast.LENGTH_SHORT).show()
                    },
                    onDelete = { selected ->
                        tryOnHistoryItems = tryOnHistoryItems.filterNot { item ->
                            selected.any { it.id == item.id }
                        }
                        Toast.makeText(context, "已从当前列表删除", Toast.LENGTH_SHORT).show()
                    },
                    onOpenResult = { openTryOnHistoryResult(it) },
                    onTryAgain = { go(Screen.TryOnUpload(it, true)) }
                )

                Screen.Favorites -> FavoritesScreen(
                    styles = styleItems.filter { favorites.contains(it.id) },
                    refreshing = pageRefreshing,
                    onRefresh = ::refreshPageData,
                    onStyleClick = { go(Screen.StyleDetail(it)) },
                    onRetake = { go(Screen.TryOnUpload(it, true)) },
                    onBook = ::openBookingForStyle
                )

                Screen.BookingRecords -> BookingRecordsScreen(
                    records = bookingRecords,
                    refreshing = pageRefreshing,
                    onRefresh = ::refreshPageData
                )

                is Screen.StoreDetail -> {
                    val store = storeItems.firstOrNull { it.id == screen.storeId } ?: return@AnimatedContent
                    StoreDetailScreen(
                        store = store,
                        onBook = {
                            selectedStoreId = store.id
                            val targetStyleId = screen.styleId ?: styleItems.firstOrNull()?.id
                            if (targetStyleId == null) {
                                Toast.makeText(context, "当前还没有可预约款式", Toast.LENGTH_SHORT).show()
                            } else {
                                go(Screen.BookingForm(store.id, targetStyleId))
                            }
                        }
                    )
                }

                is Screen.BookingForm -> {
                    val store = storeItems.firstOrNull { it.id == selectedStoreId } ?: return@AnimatedContent
                    val style = styleItems.firstOrNull { it.id == screen.styleId } ?: return@AnimatedContent
                    BookingFormScreen(
                        store = store,
                        style = style,
                        storeOptions = storeItems,
                        submitting = bookingSubmitting,
                        errorMessage = bookingError,
                        onStoreChange = { selectedStoreId = it },
                        onSubmit = { name, phone, note, slot ->
                            coroutineScope.launch {
                                bookingSubmitting = true
                                bookingError = null
                                runCatching {
                                    repository.createBooking(
                                        storeId = selectedStoreId,
                                        styleId = screen.styleId,
                                        slot = slot,
                                        name = name,
                                        phone = phone,
                                        note = note
                                    )
                                }.onSuccess { booking ->
                                    pendingBooking = booking
                                    bookingRecords = listOf(booking.toUi()) + bookingRecords.filterNot { it.id == booking.id }
                                    go(Screen.BookingConfirm(booking.id))
                                }.onFailure { error ->
                                    bookingError = error.message ?: "创建预约失败"
                                }
                                bookingSubmitting = false
                            }
                        }
                    )
                }

                is Screen.BookingConfirm -> {
                    val booking = findBooking(screen.bookingId) ?: return@AnimatedContent
                    BookingConfirmScreen(
                        booking = booking,
                        loading = bookingSubmitting,
                        errorMessage = bookingError,
                        onConfirm = {
                            coroutineScope.launch {
                                bookingSubmitting = true
                                bookingError = null
                                runCatching { repository.confirmBooking(screen.bookingId) }
                                    .onSuccess { confirmed ->
                                        pendingBooking = confirmed
                                        bookingRecords = bookingRecords.map { if (it.id == confirmed.id) confirmed.toUi() else it }
                                        go(Screen.BookingSuccess(screen.bookingId))
                                    }
                                    .onFailure { error ->
                                        bookingError = error.message ?: "确认预约失败"
                                    }
                                bookingSubmitting = false
                            }
                        }
                    )
                }

                is Screen.BookingSuccess -> BookingSuccessScreen(
                    booking = findBooking(screen.bookingId) ?: return@AnimatedContent,
                    onRecords = { go(Screen.BookingRecords) },
                    onBackHome = {
                        currentTab = MainTab.Home
                        stack.clear()
                        stack.add(Screen.Tab(MainTab.Home))
                    }
                )

                Screen.Settings -> SettingsScreen(
                    settings = userSettings,
                    onLogout = {
                        coroutineScope.launch {
                            runCatching { repository.logout() }
                            resetToLogin()
                        }
                    }
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen(
    recommended: List<NailStyle>,
    hot: List<NailStyle>,
    refreshing: Boolean,
    onRefresh: () -> Unit,
    onSearch: () -> Unit,
    onSeeMore: () -> Unit,
    onRanking: () -> Unit,
    onStyleClick: (String) -> Unit
) {
    PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            HomeHero(onSearch = onSearch)
            HomeSectionHeader(title = "推荐", actionText = "查看更多", onAction = onSeeMore)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1.35f),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                recommended.take(2).forEach { style ->
                    HomeFeaturedCard(
                        style = style,
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxSize(),
                        onClick = { onStyleClick(style.id) }
                    )
                }
                repeat((2 - recommended.take(2).size).coerceAtLeast(0)) {
                    Spacer(Modifier.weight(1f))
                }
            }
            HomeSectionHeader(title = "热门款式", actionText = "排行榜", onAction = onRanking)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                hot.take(3).forEach { style ->
                    HomeCompactCard(
                        style = style,
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxSize(),
                        onClick = { onStyleClick(style.id) }
                    )
                }
                repeat((3 - hot.take(3).size).coerceAtLeast(0)) {
                    Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun HomeHero(onSearch: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = "Nail Mind",
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "发现适合你的美甲风格",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f),
                    fontSize = 13.sp
                )
            }
            IconButton(onClick = {}) {
                Icon(
                    Icons.Rounded.NotificationsNone,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.size(23.dp)
                )
            }
        }

        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onSearch),
            color = MaterialTheme.colorScheme.surface,
            shape = MaterialTheme.shapes.medium,
            border = androidx.compose.foundation.BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outline.copy(alpha = 0.55f)
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 15.dp, vertical = 11.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    Icons.Rounded.Search,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f)
                )
                Text(
                    text = "搜索款式 / 风格 / 门店",
                    modifier = Modifier.weight(1f),
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.42f),
                    fontSize = 13.sp
                )
                Text(
                    text = "输入关键词",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.28f),
                    fontSize = 11.sp
                )
            }
        }
    }
}

@Composable
private fun HomeSectionHeader(title: String, actionText: String, onAction: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .width(3.dp)
                .height(18.dp)
                .clip(MaterialTheme.shapes.small)
                .background(MaterialTheme.colorScheme.primary)
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = title,
            fontWeight = FontWeight.Bold,
            fontSize = 21.sp
        )
        Spacer(Modifier.weight(1f))
        Row(
            modifier = Modifier.clickable(onClick = onAction),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = actionText,
                color = MaterialTheme.colorScheme.primary,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium
            )
            Icon(
                imageVector = Icons.Rounded.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(18.dp)
            )
        }
    }
}

@Composable
private fun HomeFeaturedCard(
    style: NailStyle,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.7f)
        )
    ) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            GradientThumb(
                style = style,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(0.82f)
            )
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = style.name,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 14.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = style.vibe,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f),
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun HomeCompactCard(
    style: NailStyle,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.7f)
        )
    ) {
        Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            GradientThumb(
                style = style,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(0.88f)
            )
            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(
                    text = style.name,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = style.tags.firstOrNull() ?: style.vibe,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.56f),
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun RankingScreen(styles: List<NailStyle>, onStyleClick: (String) -> Unit) {
    val rankedStyles = styles.take(12)
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            SectionHeader("热门排行榜", "根据当前站内推荐与热门款式临时排序，正式数据接入后会自动更新。")
        }
        items(rankedStyles) { style ->
            val rank = rankedStyles.indexOf(style) + 1
            RankingRow(rank = rank, style = style, onClick = { onStyleClick(style.id) })
        }
        if (rankedStyles.isEmpty()) {
            item {
                EmptyState("暂无排行榜", "款式数据加载后会自动生成榜单。")
            }
        }
    }
}

@Composable
private fun RankingRow(rank: Int, style: NailStyle, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.36f)
        )
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                color = when (rank) {
                    1 -> MaterialTheme.colorScheme.primary
                    2 -> MaterialTheme.colorScheme.primary.copy(alpha = 0.72f)
                    3 -> MaterialTheme.colorScheme.primary.copy(alpha = 0.48f)
                    else -> RoseTint
                },
                shape = MaterialTheme.shapes.medium
            ) {
                Text(
                    text = rank.toString().padStart(2, '0'),
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                    color = if (rank <= 3) MaterialTheme.colorScheme.onPrimary else RoseAccent,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp
                )
            }
            GradientThumb(style = style, modifier = Modifier.size(82.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(style.name, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(style.vibe, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.64f), fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    "热度 ${100 - rank * 3} · 试戴推荐",
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium
                )
            }
            Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.32f))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StylesScreen(
    styles: List<NailStyle>,
    refreshing: Boolean,
    onRefresh: () -> Unit,
    onStyleClick: (String) -> Unit
) {
    var selectedTab by remember { mutableStateOf(StyleBrowseTab.NailShape) }
    var selectedOption by remember { mutableStateOf(nailShapeBrowseOptions.first()) }
    var query by remember { mutableStateOf("") }
    val options = selectedTab.options()

    LaunchedEffect(selectedTab) {
        selectedOption = selectedTab.options().first()
    }

    val queryMatchedStyles = styles.filter { it.matchesStyleQuery(query) }
    val categoryMatchedStyles = queryMatchedStyles.filter { it.matchesBrowseOption(selectedTab, selectedOption) }
    val filteredStyles = categoryMatchedStyles.ifEmpty { queryMatchedStyles }

    PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
                    placeholder = { Text("输入关键词") },
                    shape = MaterialTheme.shapes.large
                )
                OutlinedButton(
                    onClick = {
                        query = ""
                        selectedOption = options.first()
                    },
                    modifier = Modifier.defaultMinSize(minHeight = 56.dp),
                    shape = MaterialTheme.shapes.medium
                ) {
                    Text("筛选")
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(MaterialTheme.shapes.medium)
                    .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.35f), MaterialTheme.shapes.medium)
            ) {
                StyleBrowseTab.values().forEach { tab ->
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .clickable { selectedTab = tab },
                        color = if (selectedTab == tab) MaterialTheme.colorScheme.primary.copy(alpha = 0.11f) else Color.Transparent
                    ) {
                        Text(
                            text = tab.title,
                            modifier = Modifier.padding(vertical = 14.dp),
                            color = if (selectedTab == tab) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                            fontSize = 16.sp,
                            fontWeight = if (selectedTab == tab) FontWeight.Bold else FontWeight.SemiBold,
                            textAlign = TextAlign.Center
                        )
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxSize(),
                horizontalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                LazyColumn(
                    modifier = Modifier
                        .width(88.dp)
                        .fillMaxSize()
                        .clip(MaterialTheme.shapes.medium)
                        .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.96f))
                        .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.22f), MaterialTheme.shapes.medium),
                    contentPadding = PaddingValues(vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    items(options) { option ->
                        val selected = selectedOption == option
                        Surface(
                            modifier = Modifier
                                .padding(horizontal = 8.dp)
                                .fillMaxWidth()
                                .clickable { selectedOption = option },
                            color = if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else Color.Transparent,
                            shape = MaterialTheme.shapes.small
                        ) {
                            Text(
                                text = option.label,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 6.dp, vertical = 13.dp),
                                color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.76f),
                                fontSize = 14.sp,
                                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }

                LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(bottom = 96.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    if (filteredStyles.isEmpty()) {
                        item {
                            EmptyState("没有匹配款式", "换个关键词，或切换到其他${selectedTab.title}小类。")
                        }
                    } else {
                        items(filteredStyles) { style ->
                            StyleGridRow(style = style, onClick = { onStyleClick(style.id) })
                        }
                    }
                }
            }
        }
    }
}

private fun StyleBrowseTab.options(): List<StyleBrowseOption> = when (this) {
    StyleBrowseTab.NailShape -> nailShapeBrowseOptions
    StyleBrowseTab.Effect -> effectBrowseOptions
    StyleBrowseTab.Vibe -> vibeBrowseOptions
}

private fun NailStyle.searchCorpus(): String =
    listOf(name, vibe, nailType, skinTone, tags.joinToString(" ")).joinToString(" ")

private fun NailStyle.matchesStyleQuery(query: String): Boolean {
    val trimmed = query.trim()
    if (trimmed.isBlank()) return true
    return searchCorpus().contains(trimmed, ignoreCase = true)
}

private fun NailStyle.matchesBrowseOption(tab: StyleBrowseTab, option: StyleBrowseOption): Boolean {
    val corpus = searchCorpus()
    if (option.keywords.any { corpus.contains(it, ignoreCase = true) }) return true
    val sequence = id.substringAfterLast("-").toIntOrNull() ?: return true
    val options = tab.options()
    return options.indexOf(option).takeIf { it >= 0 } == ((sequence - 1).floorMod(options.size))
}

private fun Int.floorMod(modulus: Int): Int = ((this % modulus) + modulus) % modulus

@Composable
private fun TryOnHubScreen(
    favorites: List<NailStyle>,
    hot: List<NailStyle>,
    systemRecommended: List<NailStyle>,
    onHotPick: (String) -> Unit,
    onFavoritePick: (String) -> Unit,
    onRecommendedPick: (String) -> Unit,
    onDiy: () -> Unit
) {
    val context = LocalContext.current
    var activePanel by remember { mutableStateOf<TryOnPanel?>(null) }
    val activeItems = when (activePanel) {
        TryOnPanel.Hot -> hot
        TryOnPanel.Favorites -> favorites
        TryOnPanel.Recommended -> systemRecommended
        null -> emptyList()
    }
    val activePick: (String) -> Unit = when (activePanel) {
        TryOnPanel.Hot -> onHotPick
        TryOnPanel.Favorites -> onFavoritePick
        TryOnPanel.Recommended -> onRecommendedPick
        null -> onHotPick
    }
    val fallbackStyle = systemRecommended.firstOrNull() ?: hot.firstOrNull() ?: favorites.firstOrNull()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 14.dp, vertical = 12.dp)
    ) {
        Card(
            modifier = Modifier.fillMaxSize(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f)),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            border = androidx.compose.foundation.BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outline.copy(alpha = 0.22f)
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(14.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(
                    modifier = Modifier.width(72.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    TryOnSideButton("热门", Icons.Rounded.Star, activePanel == TryOnPanel.Hot) { activePanel = TryOnPanel.Hot }
                    TryOnSideButton("收藏", Icons.Rounded.FavoriteBorder, activePanel == TryOnPanel.Favorites) { activePanel = TryOnPanel.Favorites }
                    TryOnSideButton("推荐", Icons.Rounded.AutoAwesome, activePanel == TryOnPanel.Recommended) { activePanel = TryOnPanel.Recommended }
                    TryOnSideButton("DIY", Icons.Rounded.BookmarkBorder, false, onDiy)
                }

                if (activePanel != null) {
                    TryOnSlideOutList(
                        title = activePanel!!.title,
                        styles = activeItems,
                        onPick = activePick,
                        modifier = Modifier.width(148.dp)
                    )
                }

                TryOnUploadIllustration(
                    modifier = Modifier.weight(1f),
                    onUpload = {
                        fallbackStyle?.let { onHotPick(it.id) }
                            ?: Toast.makeText(context, "暂无可试戴款式", Toast.LENGTH_SHORT).show()
                    }
                )

                Column(
                    modifier = Modifier.width(58.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    OutlinedButton(
                        onClick = {
                            Toast.makeText(context, "拍摄时保持手部清晰、手指自然张开、光线充足。", Toast.LENGTH_LONG).show()
                        },
                        modifier = Modifier
                            .width(54.dp)
                            .height(86.dp),
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 8.dp),
                        shape = MaterialTheme.shapes.large
                    ) {
                        Text("拍摄\n参考", textAlign = TextAlign.Center, fontSize = 13.sp, lineHeight = 18.sp)
                    }
                }
            }
        }
    }
}

private enum class TryOnPanel(val title: String) {
    Hot("热门款式"),
    Favorites("收藏款式"),
    Recommended("系统推荐")
}

@Composable
private fun TryOnSideButton(
    label: String,
    icon: ImageVector,
    selected: Boolean,
    onClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .size(width = 64.dp, height = 78.dp)
            .clickable(onClick = onClick),
        color = if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else Color.Transparent,
        shape = MaterialTheme.shapes.medium,
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = if (selected) 0.55f else 0.32f)
        )
    ) {
        Column(
            modifier = Modifier.padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(icon, contentDescription = label, modifier = Modifier.size(28.dp), tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f))
            Spacer(Modifier.height(6.dp))
            Text(label, fontSize = 13.sp, textAlign = TextAlign.Center)
        }
    }
}

@Composable
private fun TryOnSlideOutList(
    title: String,
    styles: List<NailStyle>,
    onPick: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxHeight(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.42f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.18f))
    ) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            if (styles.isEmpty()) {
                Text("暂无数据", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.56f))
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(styles.take(8)) { style ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(MaterialTheme.shapes.small)
                                .background(MaterialTheme.colorScheme.surface)
                                .clickable { onPick(style.id) }
                                .padding(7.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            GradientThumb(style = style, modifier = Modifier.size(42.dp))
                            Column(Modifier.weight(1f)) {
                                Text(style.name, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text("点击试戴", fontSize = 10.sp, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TryOnUploadIllustration(modifier: Modifier = Modifier, onUpload: () -> Unit) {
    Column(
        modifier = modifier.fillMaxHeight(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center
        ) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth(0.9f)
                    .aspectRatio(0.72f),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.34f),
                shape = MaterialTheme.shapes.large,
                border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.25f))
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(
                        Icons.Rounded.PhotoCamera,
                        contentDescription = null,
                        modifier = Modifier.size(68.dp),
                        tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.34f)
                    )
                    Spacer(Modifier.height(14.dp))
                    Text("上传手部图片开始试戴", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f), fontSize = 15.sp)
                }
            }
        }
        OutlinedButton(
            onClick = onUpload,
            modifier = Modifier
                .fillMaxWidth(0.82f)
                .height(56.dp),
            shape = MaterialTheme.shapes.medium
        ) {
            Icon(Icons.Rounded.PhotoCamera, contentDescription = null, modifier = Modifier.size(26.dp))
            Spacer(Modifier.width(12.dp))
            Text("拍照上传", fontSize = 18.sp)
        }
    }
}

@Composable
private fun DiyDesignerScreen(onSave: () -> Unit, onTryOn: () -> Unit) {
    val shapes = listOf("小短梯", "短方圆", "中方", "中椭圆", "中短梯", "长梯", "长椭圆", "尖水滴")
    val colors = listOf("奶油白", "樱花粉", "豆沙粉", "酒红", "雾霾蓝", "玫瑰金")
    var selectedShape by remember { mutableStateOf(shapes.first()) }
    var designStep by remember { mutableStateOf(0) }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            SectionHeader(
                if (designStep == 0) "选择甲型" else "设计款式",
                if (designStep == 0) "先选择一种甲型，下一步再设计颜色、样式和装饰。" else "DIY功能先做基础流程，后续会加入手绘画布和装饰素材。"
            )
        }
        if (designStep == 0) {
            items(shapes.chunked(3)) { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    row.forEach { shape ->
                        FilterPill(
                            text = shape,
                            selected = selectedShape == shape,
                            modifier = Modifier.weight(1f)
                        ) { selectedShape = shape }
                    }
                }
            }
            item {
                Button(onClick = { designStep = 1 }, modifier = Modifier.fillMaxWidth()) { Text("下一步") }
            }
        } else {
            item { CompactValue("当前甲型", selectedShape) }
            item { DiyChoiceRow("设计颜色", colors) }
            item { DiyChoiceRow("样式", listOf("纯色", "法式", "渐变", "猫眼", "手绘")) }
            item { DiyChoiceRow("装饰物", listOf("珍珠", "钻饰", "星星", "蝴蝶结", "贴纸")) }
            item {
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(170.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f),
                    shape = MaterialTheme.shapes.large,
                    border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.25f))
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text("手绘区域预留", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.56f))
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(onClick = onSave, modifier = Modifier.weight(1f)) { Text("保存款式") }
                    Button(onClick = onTryOn, modifier = Modifier.weight(1f)) { Text("直接试戴") }
                }
            }
        }
    }
}

@Composable
private fun DiyChoiceRow(title: String, options: List<String>) {
    var selected by remember { mutableStateOf(options.firstOrNull().orEmpty()) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            options.forEach { option ->
                FilterPill(text = option, selected = selected == option) { selected = option }
            }
        }
    }
}

@Composable
private fun FilterPill(text: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Surface(
        modifier = modifier.clickable(onClick = onClick),
        color = if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.14f) else MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.medium,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.32f))
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 12.dp),
            textAlign = TextAlign.Center,
            color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
        )
    }
}

@Composable
private fun BookingScreen(stores: List<Store>, onStoreClick: (String) -> Unit) {
    if (stores.isEmpty()) {
        EmptyState("暂无可预约门店", "接入真实门店数据后，这里会展示支持预约的门店与时段。")
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item { SectionHeader("附近门店", "可直接查看时段与作品风格") }
        items(stores) { store ->
            StoreCard(store = store, onClick = { onStoreClick(store.id) })
        }
    }
}

@Composable
private fun ProfileScreen(
    user: AuthUser,
    favoritesCount: Int,
    tryOnHistoryCount: Int,
    onFavorites: () -> Unit,
    onTryOnHistory: () -> Unit,
    onRecords: () -> Unit,
    onSettings: () -> Unit
) {
    val context = LocalContext.current
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 20.dp, top = 18.dp, end = 20.dp, bottom = 112.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    modifier = Modifier.size(74.dp),
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.14f),
                    shape = MaterialTheme.shapes.large
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            text = user.name.take(1).ifBlank { "N" },
                            color = MaterialTheme.colorScheme.primary,
                            fontSize = 30.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(user.name, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Text(user.email, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f), fontSize = 14.sp)
                }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                ProfileQuickCard(
                    title = "我的收藏",
                    subtitle = "$favoritesCount 个款式",
                    icon = Icons.Rounded.FavoriteBorder,
                    modifier = Modifier.weight(1f),
                    onClick = onFavorites
                )
                ProfileQuickCard(
                    title = "试戴记录",
                    subtitle = "$tryOnHistoryCount 条记录",
                    icon = Icons.Rounded.AutoAwesome,
                    modifier = Modifier.weight(1f),
                    onClick = onTryOnHistory
                )
            }
        }
        item {
            ProfileMenuRow(
                title = "我的作品",
                subtitle = "查看已保存的 DIY 设计与试戴作品",
                icon = Icons.Rounded.GridView,
                onClick = { Toast.makeText(context, "我的作品功能待接入", Toast.LENGTH_SHORT).show() }
            )
        }
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Text("我的预约", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Row(horizontalArrangement = Arrangement.SpaceAround, modifier = Modifier.fillMaxWidth()) {
                        ProfileActionIcon("订单", Icons.Rounded.CalendarMonth, onRecords)
                        ProfileActionIcon("评价", Icons.Rounded.Star) {
                            Toast.makeText(context, "评价功能待接入", Toast.LENGTH_SHORT).show()
                        }
                        ProfileActionIcon("售后", Icons.Rounded.Storefront) {
                            Toast.makeText(context, "售后功能待接入", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("更多功能", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                ProfileMenuRow("Like", "查看你点赞过的款式内容", Icons.Rounded.FavoriteBorder) {
                    Toast.makeText(context, "Like 功能待接入", Toast.LENGTH_SHORT).show()
                }
                ProfileMenuRow("风格档案", "管理肤色、偏好和常用甲型", Icons.Rounded.Person) {
                    Toast.makeText(context, "风格档案功能待接入", Toast.LENGTH_SHORT).show()
                }
                ProfileMenuRow("消息中心", "查看通知、预约提醒和系统消息", Icons.Rounded.NotificationsNone) {
                    Toast.makeText(context, "消息中心功能待接入", Toast.LENGTH_SHORT).show()
                }
                ProfileMenuRow("设置", "通知、隐私与偏好设置", Icons.Rounded.Storefront, onSettings)
            }
        }
    }
}

@Composable
private fun ProfileQuickCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.22f))
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
            Text(title, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            Text(subtitle, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f), fontSize = 12.sp)
        }
    }
}

@Composable
private fun ProfileActionIcon(title: String, icon: ImageVector, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .clip(MaterialTheme.shapes.medium)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Icon(icon, contentDescription = title, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
        Text(title, fontSize = 13.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun ProfileMenuRow(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.18f))
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Surface(
                modifier = Modifier.size(42.dp),
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.1f),
                shape = MaterialTheme.shapes.medium
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(23.dp))
                }
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f), fontSize = 12.sp)
            }
            Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.34f))
        }
    }
}

@Composable
private fun StyleDetailScreen(
    style: NailStyle,
    favorite: Boolean,
    onToggleFavorite: () -> Unit,
    onTryOn: () -> Unit,
    onBook: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 20.dp, top = 20.dp, end = 20.dp, bottom = 104.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                GradientThumb(style = style, modifier = Modifier.fillMaxWidth().aspectRatio(1.08f))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center
                ) {
                    repeat(4) { index ->
                        Box(
                            modifier = Modifier
                                .padding(horizontal = 4.dp)
                                .size(if (index == 0) 8.dp else 6.dp)
                                .clip(MaterialTheme.shapes.small)
                                .background(
                                    if (index == 0) MaterialTheme.colorScheme.primary
                                    else MaterialTheme.colorScheme.outline.copy(alpha = 0.45f)
                                )
                        )
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(style.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                TagRow(style.tags)
            }
        }
        item {
            DetailTextSection(
                title = "款式介绍",
                body = "温柔法式设计，奶白色打底搭配细腻勾边，通勤显白不挑肤色。简约耐看，日常通勤与约会都能轻松驾驭。"
            )
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("用户评价", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                ReviewCard(
                    author = "小鹿酱",
                    rating = 5,
                    body = "颜色很温柔，显白又百搭，通勤约会都很合适！短甲也能撑起来，越看越喜欢。",
                    style = style
                )
                ReviewCard(
                    author = "甜甜圈",
                    rating = 5,
                    body = "很显手干净，法式边缘做得很细致。做完上手后照明间变精致了。",
                    style = style
                )
            }
        }
    }
}

@Composable
private fun DetailMetricCard(entries: List<Pair<String, String>>) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)
        )
    ) {
        Row(modifier = Modifier.fillMaxWidth()) {
            entries.forEachIndexed { index, (label, value) ->
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .padding(horizontal = 12.dp, vertical = 16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text(
                        text = label,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
                    )
                    Text(
                        text = value,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp
                    )
                }
                if (index != entries.lastIndex) {
                    Box(
                        modifier = Modifier
                            .padding(vertical = 14.dp)
                            .width(1.dp)
                            .height(42.dp)
                            .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.45f))
                    )
                }
            }
        }
    }
}

@Composable
private fun DetailTextSection(title: String, body: String) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(
                body,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f),
                fontSize = 13.sp,
                lineHeight = 20.sp
            )
        }
    }
}

@Composable
private fun ReviewCard(
    author: String,
    rating: Int,
    body: String,
    style: NailStyle
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)
        )
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            GradientThumb(
                style = style,
                modifier = Modifier
                    .size(72.dp)
                    .clip(MaterialTheme.shapes.small)
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(author, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    Row(horizontalArrangement = Arrangement.spacedBy(1.dp)) {
                        repeat(rating) {
                            Icon(
                                Icons.Rounded.Star,
                                contentDescription = null,
                                tint = Color(0xFFFFB84D),
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    }
                }
                Text(
                    body,
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f),
                    lineHeight = 18.sp
                )
            }
        }
    }
}

@Composable
private fun SearchScreen(hotKeywords: List<String>, onSearch: (String) -> Unit) {
    var query by remember { mutableStateOf("") }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("输入关键词") },
            trailingIcon = {
                IconButton(onClick = { onSearch(query.ifBlank { hotKeywords.first() }) }) {
                    Icon(Icons.Rounded.Search, contentDescription = "搜索")
                }
            }
        )
        Text("热门搜索", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.horizontalScroll(rememberScrollState())) {
            hotKeywords.forEach {
                AssistChip(
                    onClick = { onSearch(it) },
                    label = { Text(it) },
                    colors = AssistChipDefaults.assistChipColors(containerColor = MaterialTheme.colorScheme.surface)
                )
            }
        }
    }
}

@Composable
private fun SearchResultScreen(query: String, result: List<NailStyle>, onStyleClick: (String) -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Text("“$query” 的结果", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        items(result) { style ->
            HotListItem(style = style, onClick = { onStyleClick(style.id) })
        }
    }
}

@Composable
private fun TryOnUploadScreen(
    style: NailStyle,
    fromFavorites: Boolean,
    loading: Boolean,
    errorMessage: String?,
    lastSourceFile: File?,
    onStartProcessing: (File, String) -> Unit
) {
    val context = LocalContext.current
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap ->
        if (bitmap != null) {
            onStartProcessing(saveBitmapToCache(context, bitmap), "camera")
        }
    }
    val galleryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            val file = copyUriToCache(context, uri)
            if (file != null) {
                onStartProcessing(file, "gallery")
            } else {
                Toast.makeText(context, "读取图片失败，请重试", Toast.LENGTH_SHORT).show()
            }
        }
    }
    val cameraPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            cameraLauncher.launch(null)
        } else {
            Toast.makeText(context, "未授予相机权限，无法拍照试戴", Toast.LENGTH_SHORT).show()
        }
    }
    val galleryPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            galleryLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        } else {
            Toast.makeText(context, "未授予相册权限，无法选择图片", Toast.LENGTH_SHORT).show()
        }
    }

    fun openCamera() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            cameraLauncher.launch(null)
        } else {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    fun openGallery() {
        val permission = galleryPermission()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU || ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED) {
            galleryLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        } else {
            galleryPermissionLauncher.launch(permission)
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        item {
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(style.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(
                        if (fromFavorites) "来自我的收藏，试戴效果会一并保存。" else "当前选择的试戴款式。",
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                    )
                }
            }
        }
        item {
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("上传提示", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("请保持手部清晰、手指自然张开、光线充足，并尽量露出完整指甲。", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f))
                    if (!errorMessage.isNullOrBlank()) {
                        Text(errorMessage, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(onClick = ::openCamera, modifier = Modifier.weight(1f), enabled = !loading) { Text(if (loading) "处理中..." else "拍照") }
                        OutlinedButton(onClick = ::openGallery, modifier = Modifier.weight(1f), enabled = !loading) { Text("从相册上传") }
                    }
                    TextButton(onClick = { lastSourceFile?.let { onStartProcessing(it, "history") } }, enabled = !loading && lastSourceFile != null) { Text("使用上次手部照片") }
                }
            }
        }
    }
}

@Composable
private fun TryOnProcessingScreen(
    stage: String,
    progress: Int,
    errorMessage: String?,
    onDone: () -> Unit,
    onLeave: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(
                Modifier.padding(28.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                CircularProgressIndicator()
                Text("正在生成你的试戴效果", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("当前进度: ${stageLabel(stage)} · $progress%", textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f))
                Text(
                    "你可以先去浏览其他款式，结果生成后会保存在试戴记录里。",
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                    fontSize = 13.sp
                )
                errorMessage?.takeIf { it.isNotBlank() }?.let {
                    Text(it, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.error)
                }
                if (progress >= 100 && errorMessage.isNullOrBlank()) {
                    Button(onClick = onDone) { Text("查看试戴结果") }
                } else {
                    OutlinedButton(onClick = onLeave) { Text("先去逛逛，稍后查看") }
                }
            }
        }
    }
}

@Composable
private fun TryOnResultScreen(
    style: NailStyle,
    favorite: Boolean,
    resultStatus: String,
    resultBitmap: Bitmap?,
    onOpenStyle: () -> Unit,
    onRetake: () -> Unit,
    onToggleFavorite: () -> Unit,
    onBook: () -> Unit,
    onSaveImage: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        item {
            ResultCanvas(style = style, resultBitmap = resultBitmap)
        }
        item {
            Text(style.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        item {
            Text(
                if (resultStatus == "completed" || resultStatus.isBlank()) "试戴图已生成，可查看上手效果并决定是否预约同款。" else "试戴结果暂不可用，请重新上传手部照片后再试。",
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f)
            )
        }
        item {
            OutlinedButton(
                onClick = onOpenStyle,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("查看款式详情")
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onRetake, modifier = Modifier.weight(1f)) { Text("重新上传") }
                OutlinedButton(onClick = onToggleFavorite, modifier = Modifier.weight(1f)) { Text(if (favorite) "已收藏" else "收藏款式") }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = onBook, modifier = Modifier.weight(1f)) { Text("预约同款") }
                OutlinedButton(
                    onClick = onSaveImage,
                    modifier = Modifier.weight(1f),
                    enabled = resultBitmap != null
                ) { Text("保存图片") }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TryOnHistoryScreen(
    items: List<TryOnHistoryItemDto>,
    styles: List<NailStyle>,
    refreshing: Boolean,
    manageMode: Boolean,
    onRefresh: () -> Unit,
    onShare: (List<TryOnHistoryItemDto>) -> Unit,
    onMoveToFavorites: (List<TryOnHistoryItemDto>) -> Unit,
    onDelete: (List<TryOnHistoryItemDto>) -> Unit,
    onOpenResult: (TryOnHistoryItemDto) -> Unit,
    onTryAgain: (String) -> Unit
) {
    val selectedIds = remember { mutableStateListOf<String>() }
    LaunchedEffect(manageMode, items) {
        if (!manageMode) selectedIds.clear()
        selectedIds.removeAll { id -> items.none { it.id == id } }
    }
    if (items.isEmpty()) {
        EmptyState("还没有试戴记录", "上传一张手部照片后，生成过的效果图都会保存在这里。")
        return
    }
    PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        Box(Modifier.fillMaxSize()) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 20.dp, top = 20.dp, end = 20.dp, bottom = if (manageMode) 132.dp else 20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                items(items) { item ->
                    val selected = selectedIds.contains(item.id)
                    TryOnHistoryCard(
                        item = item,
                        manageMode = manageMode,
                        selected = selected,
                        onToggleSelected = {
                            if (selected) selectedIds.remove(item.id) else selectedIds.add(item.id)
                        },
                        onOpenResult = { onOpenResult(item) },
                        onTryAgain = { onTryAgain(item.styleId) }
                    )
                }
            }
            if (manageMode) {
                val selectedItems = items.filter { selectedIds.contains(it.id) }
                TryOnHistoryManageBar(
                    allSelected = selectedIds.size == items.size,
                    selectedCount = selectedItems.size,
                    onToggleAll = {
                        if (selectedIds.size == items.size) {
                            selectedIds.clear()
                        } else {
                            selectedIds.clear()
                            selectedIds.addAll(items.map { it.id })
                        }
                    },
                    onShare = { onShare(selectedItems) },
                    onMoveToFavorites = { onMoveToFavorites(selectedItems) },
                    onDelete = {
                        onDelete(selectedItems)
                        selectedIds.clear()
                    },
                    modifier = Modifier.align(Alignment.BottomCenter)
                )
            }
        }
    }
}

@Composable
private fun TryOnHistoryCard(
    item: TryOnHistoryItemDto,
    manageMode: Boolean,
    selected: Boolean,
    onToggleSelected: () -> Unit,
    onOpenResult: () -> Unit,
    onTryAgain: () -> Unit
) {
    val isPending = item.source == "pending" || item.resultUrl.isBlank()
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(enabled = manageMode, onClick = onToggleSelected)
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (manageMode) {
                Checkbox(checked = selected, onCheckedChange = { onToggleSelected() })
            }
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Box(
                        modifier = Modifier
                            .size(92.dp)
                            .clip(MaterialTheme.shapes.medium)
                            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
                    ) {
                        SubcomposeAsyncImage(
                            model = item.resultUrl.takeIf { it.isNotBlank() },
                            contentDescription = item.styleName,
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Crop
                        ) {
                            when (painter.state) {
                                is AsyncImagePainter.State.Success -> SubcomposeAsyncImageContent()
                                else -> Column(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .padding(10.dp),
                                    verticalArrangement = Arrangement.Center,
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Icon(
                                        imageVector = Icons.Rounded.AutoAwesome,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.8f),
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(Modifier.height(6.dp))
                                    Text(
                                        text = if (isPending) "生成中" else "结果待查看",
                                        fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        }
                    }
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Text(item.styleName, fontWeight = FontWeight.SemiBold)
                        Text(
                            if (isPending) "试戴结果生成中" else "最近一次试戴结果",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f)
                        )
                        Text(
                            item.createdAt.take(16).replace('T', ' '),
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.52f)
                        )
                    }
                }
                if (!manageMode) {
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedButton(
                            onClick = onOpenResult,
                            modifier = Modifier.weight(1f),
                            enabled = !isPending
                        ) {
                            Text("查看结果")
                        }
                        Button(onClick = onTryAgain, modifier = Modifier.weight(1f)) {
                            Text("再次试戴")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TryOnHistoryManageBar(
    allSelected: Boolean,
    selectedCount: Int,
    onToggleAll: () -> Unit,
    onShare: () -> Unit,
    onMoveToFavorites: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .navigationBarsPadding(),
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 12.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.clickable(onClick = onToggleAll),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(checked = allSelected, onCheckedChange = { onToggleAll() })
                Text("全选", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f))
            }
            Spacer(Modifier.weight(1f))
            OutlinedButton(onClick = onShare, enabled = selectedCount > 0) {
                Text("分享")
            }
            OutlinedButton(onClick = onMoveToFavorites, enabled = selectedCount > 0) {
                Text("移入收藏")
            }
            Button(
                onClick = onDelete,
                enabled = selectedCount > 0,
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF2D55))
            ) {
                Icon(Icons.Rounded.Delete, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text("删除")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FavoritesScreen(
    styles: List<NailStyle>,
    refreshing: Boolean,
    onRefresh: () -> Unit,
    onStyleClick: (String) -> Unit,
    onRetake: (String) -> Unit,
    onBook: (String) -> Unit
) {
    if (styles.isEmpty()) {
        EmptyState("还没有收藏", "在款式详情页或试戴结果页收藏喜欢的款式。")
        return
    }
    PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            items(styles) { style ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            GradientThumb(style = style, modifier = Modifier.size(88.dp))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(style.name, fontWeight = FontWeight.SemiBold)
                                Text("收藏的款式会保存在这里，方便你再次试戴或预约。", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f), fontSize = 13.sp)
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            OutlinedButton(onClick = { onStyleClick(style.id) }, modifier = Modifier.weight(1f)) { Text("查看详情") }
                            OutlinedButton(onClick = { onRetake(style.id) }, modifier = Modifier.weight(1f)) { Text("再次试戴") }
                            Button(onClick = { onBook(style.id) }, modifier = Modifier.weight(1f)) { Text("预约") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StoreDetailScreen(store: Store, onBook: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        item {
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(store.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text("${store.distance} · 评分 ${store.score}")
                    TagRow(store.slots)
                }
            }
        }
        item {
            InfoGrid(
                listOf(
                    "营业时间" to store.openHours,
                    "美甲师" to "${store.artists} 位可预约",
                    "门店作品" to store.works
                )
            )
        }
        item {
            Button(onClick = onBook, modifier = Modifier.fillMaxWidth()) { Text("立即预约") }
        }
    }
}

@Composable
private fun BookingFormScreen(
    store: Store,
    style: NailStyle,
    storeOptions: List<Store>,
    submitting: Boolean,
    errorMessage: String?,
    onStoreChange: (String) -> Unit,
    onSubmit: (String, String, String, String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    val selectedSlot = store.slots.first()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { SectionHeader("预约信息", "系统已带入款式和门店信息") }
        item { CompactValue("预约款式", style.name) }
        item { CompactValue("预约门店", store.name) }
        item { CompactValue("可选时间", selectedSlot) }
        item {
            OutlinedTextField(value = name, onValueChange = { name = it }, modifier = Modifier.fillMaxWidth(), label = { Text("联系人姓名") })
        }
        item {
            OutlinedTextField(value = phone, onValueChange = { phone = it }, modifier = Modifier.fillMaxWidth(), label = { Text("手机号") })
        }
        item {
            OutlinedTextField(
                value = note,
                onValueChange = { note = it },
                modifier = Modifier.fillMaxWidth().defaultMinSize(minHeight = 120.dp),
                label = { Text("备注") }
            )
        }
        if (!errorMessage.isNullOrBlank()) {
            item {
                Text(errorMessage, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
            }
        }
        item {
            TextButton(onClick = { storeOptions.firstOrNull { it.id != store.id }?.let { onStoreChange(it.id) } }) { Text("切换其他门店") }
        }
        item {
            Button(onClick = { onSubmit(name, phone, note, selectedSlot) }, modifier = Modifier.fillMaxWidth(), enabled = !submitting) { Text(if (submitting) "提交中..." else "提交预约") }
        }
    }
}

@Composable
private fun BookingConfirmScreen(booking: BookingDto, loading: Boolean, errorMessage: String?, onConfirm: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { SectionHeader("确认订单", "请确认到店时间与门店信息") }
        item {
            InfoGrid(
                listOf(
                    "款式" to booking.styleName,
                    "门店" to booking.storeName,
                    "时间" to booking.slot
                )
            )
        }
        if (!errorMessage.isNullOrBlank()) {
            item {
                Text(errorMessage, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
            }
        }
        item {
            Button(onClick = onConfirm, modifier = Modifier.fillMaxWidth(), enabled = !loading) { Text(if (loading) "确认中..." else "确认预约") }
        }
    }
}

@Composable
private fun BookingSuccessScreen(booking: BookingDto, onRecords: () -> Unit, onBackHome: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(
                Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("预约成功", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text("到店时间 ${booking.slot}\n${booking.storeName}", textAlign = TextAlign.Center)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = onRecords) { Text("查看预约记录") }
                    Button(onClick = onBackHome) { Text("返回首页") }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BookingRecordsScreen(
    records: List<BookingRecord>,
    refreshing: Boolean,
    onRefresh: () -> Unit
) {
    if (records.isEmpty()) {
        EmptyState("暂无预约记录", "完成预约后，这里会展示到店时间、门店和状态。")
        return
    }
    PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            items(records) { record ->
                CompactActionCard(
                    title = "${record.status} | ${record.slot}",
                    subtitle = "${record.storeName} · ${record.styleName}",
                    primary = "查看门店",
                    secondary = "再次预约",
                    onPrimary = {},
                    onSecondary = {}
                )
            }
        }
    }
}

@Composable
private fun SettingsScreen(settings: UserSettings, onLogout: () -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { CompactValue("风格偏好", settings.stylePreferences) }
        item { CompactValue("消息通知", settings.notifications) }
        item { CompactValue("隐私设置", settings.privacy) }
        item {
            Button(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            ) {
                Text("退出登录", color = MaterialTheme.colorScheme.onError)
            }
        }
    }
}

@Composable
private fun AuthScreen(
    title: String,
    subtitle: String,
    primaryLabel: String,
    secondaryLabel: String,
    initialName: String,
    initialEmail: String,
    initialPassword: String,
    showNameField: Boolean,
    loading: Boolean,
    errorMessage: String?,
    onPrimary: (String, String, String) -> Unit,
    onSecondary: () -> Unit
) {
    var name by remember { mutableStateOf(initialName) }
    var email by remember { mutableStateOf(initialEmail) }
    var password by remember { mutableStateOf(initialPassword) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(subtitle, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                }
                if (showNameField) {
                    OutlinedTextField(
                        value = name,
                        onValueChange = { name = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("昵称") }
                    )
                }
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("邮箱") }
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("密码") }
                )
                if (!errorMessage.isNullOrBlank()) {
                    Text(
                        text = errorMessage,
                        color = MaterialTheme.colorScheme.error,
                        fontSize = 13.sp
                    )
                }
                Button(
                    onClick = { onPrimary(name, email, password) },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !loading
                ) {
                    Text(if (loading) "处理中..." else primaryLabel)
                }
                TextButton(onClick = onSecondary, modifier = Modifier.align(Alignment.End), enabled = !loading) {
                    Text(secondaryLabel)
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(subtitle, color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.68f))
    }
}

@Composable
private fun StyleCard(style: NailStyle, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            GradientThumb(style = style, modifier = Modifier.fillMaxWidth().aspectRatio(0.88f))
            Text(style.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(style.vibe, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f), fontSize = 13.sp, maxLines = 2)
        }
    }
}

@Composable
private fun HomeStyleCard(style: NailStyle, label: String, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .width(220.dp)
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            GradientThumb(style = style, modifier = Modifier.fillMaxWidth().aspectRatio(1.02f))
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(style.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text(style.vibe, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f), fontSize = 13.sp, maxLines = 2)
            }
            Text(label, color = MaterialTheme.colorScheme.primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun PrototypeHomeRow(style: NailStyle, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        GradientThumb(style = style, modifier = Modifier.size(72.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(style.name, fontWeight = FontWeight.SemiBold)
            Text(
                "款式详情",
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.62f)
            )
        }
        Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.28f))
    }
}

@Composable
private fun StyleGridRow(style: NailStyle, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(MaterialTheme.colorScheme.surface)
            .clickable(onClick = onClick)
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        GradientThumb(style = style, modifier = Modifier.size(92.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(style.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(style.vibe, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f), maxLines = 2)
            TagRow(style.tags)
        }
    }
}

@Composable
private fun HotListItem(style: NailStyle, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(MaterialTheme.colorScheme.surface)
            .clickable(onClick = onClick)
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        GradientThumb(style = style, modifier = Modifier.size(76.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(style.name, fontWeight = FontWeight.SemiBold)
            Text(style.vibe, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
        }
        Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f))
    }
}

@Composable
private fun HomeHotItem(style: NailStyle, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(MaterialTheme.colorScheme.surface)
            .clickable(onClick = onClick)
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        GradientThumb(style = style, modifier = Modifier.size(72.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(style.name, fontWeight = FontWeight.SemiBold)
            Text(
                style.tags.joinToString(" · "),
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.62f),
                maxLines = 1
            )
            Text(
                "点击查看款式详情",
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.primary
            )
        }
        Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f))
    }
}

@Composable
private fun PrototypeHotRow(style: NailStyle, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        GradientThumb(style = style, modifier = Modifier.size(72.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(style.name, fontWeight = FontWeight.SemiBold)
            Text(
                "款式详情",
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.62f)
            )
        }
        Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.28f))
    }
}

@Composable
private fun StoreCard(store: Store, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Storefront, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(store.name, fontWeight = FontWeight.SemiBold)
                    Text(store.distance, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                }
                Text(store.score, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
            }
            TagRow(store.slots)
        }
    }
}

@Composable
private fun TagRow(tags: List<String>) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.horizontalScroll(rememberScrollState())) {
        tags.forEach { tag ->
            Surface(
                color = RoseTint,
                shape = MaterialTheme.shapes.small
            ) {
                Text(
                    tag,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    color = RoseAccent,
                    fontSize = 12.sp
                )
            }
        }
    }
}

@Composable
private fun GradientThumb(style: NailStyle, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(MaterialTheme.shapes.medium)
            .background(Brush.linearGradient(style.colors))
            .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.45f), MaterialTheme.shapes.medium)
    ) {
        val imageUrl = style.imageUrl
        if (!imageUrl.isNullOrBlank()) {
            SubcomposeAsyncImage(
                model = imageUrl,
                contentDescription = style.name,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize()
            ) {
                when (painter.state) {
                    is AsyncImagePainter.State.Success -> SubcomposeAsyncImageContent()
                    else -> Canvas(modifier = Modifier.fillMaxSize()) {
                        val stroke = size.minDimension / 7f
                        repeat(5) { index ->
                            val step = size.width / 6
                            drawLine(
                                color = Color.White.copy(alpha = 0.24f + index * 0.05f),
                                start = Offset(step * (index + 1), size.height * 0.18f),
                                end = Offset(step * (index + 1), size.height * 0.82f),
                                strokeWidth = stroke,
                                cap = StrokeCap.Round
                            )
                        }
                    }
                }
            }
        } else {
            Canvas(modifier = Modifier.fillMaxSize()) {
                val stroke = size.minDimension / 7f
                repeat(5) { index ->
                    val step = size.width / 6
                    drawLine(
                        color = Color.White.copy(alpha = 0.24f + index * 0.05f),
                        start = Offset(step * (index + 1), size.height * 0.18f),
                        end = Offset(step * (index + 1), size.height * 0.82f),
                        strokeWidth = stroke,
                        cap = StrokeCap.Round
                    )
                }
            }
        }
    }
}

@Composable
private fun ResultCanvas(style: NailStyle, resultBitmap: Bitmap?) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(0.88f)
                .padding(18.dp)
        ) {
            if (resultBitmap != null) {
                Image(
                    bitmap = resultBitmap.asImageBitmap(),
                    contentDescription = "AI试戴结果",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(MaterialTheme.shapes.large)
                )
            } else {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(MaterialTheme.shapes.large)
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f))
                        .padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(
                        imageVector = Icons.Rounded.AutoAwesome,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.8f),
                        modifier = Modifier.size(30.dp)
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = "试戴图生成后会显示在这里",
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f),
                        textAlign = TextAlign.Center
                    )
                }
            }
            Text(
                if (resultBitmap != null) "AI 试戴结果" else "等待试戴结果",
                modifier = Modifier.align(Alignment.BottomCenter),
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f)
            )
        }
    }
}

@Composable
private fun InfoGrid(entries: List<Pair<String, String>>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        entries.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                row.forEach { (label, value) ->
                    Card(
                        modifier = Modifier.weight(1f),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                    ) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(label, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.62f), fontSize = 12.sp)
                            Text(value, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun CompactActionCard(
    title: String,
    subtitle: String,
    primary: String,
    secondary: String?,
    onPrimary: () -> Unit,
    onSecondary: () -> Unit = {}
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(subtitle, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = onPrimary, modifier = Modifier.weight(1f)) { Text(primary) }
                if (secondary != null) {
                    OutlinedButton(onClick = onSecondary, modifier = Modifier.weight(1f)) { Text(secondary) }
                }
            }
        }
    }
}

@Composable
private fun ProfileEntry(title: String, subtitle: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(MaterialTheme.colorScheme.surface)
            .clickable(onClick = onClick)
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(subtitle, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f), fontSize = 13.sp)
        }
        Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f))
    }
}

@Composable
private fun CompactValue(label: String, value: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(label, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
            Text(value, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun EmptyState(title: String, subtitle: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(
                Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(Icons.Rounded.BookmarkBorder, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(subtitle, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f))
            }
        }
    }
}
