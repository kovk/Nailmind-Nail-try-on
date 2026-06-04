package com.nailmind.app.ui

import android.Manifest
import android.content.Intent
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
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
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilterChip
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
import com.nailmind.app.data.api.AuthResponse
import com.nailmind.app.data.api.AuthUserDto
import com.nailmind.app.data.api.BookingDto
import com.nailmind.app.data.api.HomeResponse
import com.nailmind.app.data.api.NailMindApiClient
import com.nailmind.app.data.api.NailMindRepository
import com.nailmind.app.data.api.SettingsResponse
import com.nailmind.app.data.api.StoreDto
import com.nailmind.app.data.api.StyleDto
import com.nailmind.app.data.api.TryOnJobDto
import com.nailmind.app.data.config.AppConfig
import com.nailmind.app.ui.theme.RoseAccent
import com.nailmind.app.ui.theme.RoseTint
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import kotlinx.coroutines.delay
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
    data class TryOnUpload(val styleId: String, val fromFavorites: Boolean = false) : Screen
    data class TryOnProcessing(val styleId: String, val jobId: String) : Screen
    data class TryOnResult(val styleId: String, val jobId: String) : Screen
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
    val tags: List<String>
)

private data class Store(
    val id: String,
    val name: String,
    val distance: String,
    val priceBand: String,
    val score: String,
    val slots: List<String>
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
    val stage: String = "",
    val progress: Int = 0,
    val status: String = "",
    val errorMessage: String? = null
)

private val styles = listOf(
    NailStyle(
        id = "rose-mist",
        name = "玫雾法式",
        vibe = "显白, 通勤, 细闪",
        price = "￥228",
        nailType = "方圆甲",
        skinTone = "黄一白到自然肤色",
        colors = listOf(Color(0xFFF8C7D6), Color(0xFFFFEEF4), Color(0xFF9B6474)),
        tags = listOf("推荐", "显白", "法式")
    ),
    NailStyle(
        id = "tea-amber",
        name = "茶珀猫眼",
        vibe = "温柔, 气质, 轻奢",
        price = "￥268",
        nailType = "杏仁甲",
        skinTone = "自然肤色到暖肤",
        colors = listOf(Color(0xFFDFA36E), Color(0xFF7F4C2E), Color(0xFFFFE2C3)),
        tags = listOf("热门", "猫眼", "秋冬")
    ),
    NailStyle(
        id = "jade-ink",
        name = "青玉新中式",
        vibe = "新中式, 高级, 清透",
        price = "￥288",
        nailType = "椭圆甲",
        skinTone = "冷白皮到自然肤色",
        colors = listOf(Color(0xFF5F8A81), Color(0xFFDCEFE7), Color(0xFF1F403A)),
        tags = listOf("新中式", "收藏高", "节日")
    )
)

private val stores = listOf(
    Store("s1", "Nail Mind 静安店", "1.2km", "￥198-￥398", "4.9", listOf("今天 19:00", "明天 11:30", "明天 14:00")),
    Store("s2", "Nail Mind 徐汇店", "2.7km", "￥228-￥468", "4.8", listOf("今天 20:00", "明天 10:00", "明天 16:30")),
    Store("s3", "Nail Mind 浦东店", "4.3km", "￥188-￥328", "4.7", listOf("明天 09:30", "明天 13:00", "周二 18:30"))
)

private val defaultHotKeywords = listOf("法式", "显白", "新中式", "短甲", "猫眼")

private fun StyleDto.toUi(): NailStyle = NailStyle(
    id = id,
    name = name,
    vibe = vibe,
    price = price,
    nailType = nailType,
    skinTone = skinTone,
    colors = colors.map { Color(android.graphics.Color.parseColor(it)) },
    tags = tags
)

private fun StoreDto.toUi(): Store = Store(
    id = id,
    name = name,
    distance = distance,
    priceBand = priceBand,
    score = score,
    slots = slots
)

private fun AuthUserDto.toUi(): AuthUser = AuthUser(name = name, email = email, preferences = preferences)

private fun BookingDto.toUi(): BookingRecord = BookingRecord(
    id = id,
    status = status,
    storeName = storeName,
    styleName = styleName,
    slot = slot
)

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
    var selectedStoreId by remember { mutableStateOf(stores.first().id) }
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
    var userSettings by remember {
        mutableStateOf(
            UserSettings(
                stylePreferences = "显白、法式、新中式",
                notifications = "试戴完成、预约提醒、活动通知",
                privacy = "手部照片仅用于试戴与订单关联"
            )
        )
    }
    var searchResults by remember { mutableStateOf(styleItems) }
    var tryOnStatus by remember { mutableStateOf(TryOnStatus()) }
    var latestTryOnJob by remember { mutableStateOf<TryOnJobDto?>(null) }
    var latestTryOnBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var lastTryOnSourceFile by remember { mutableStateOf<File?>(null) }
    var bookingSubmitting by remember { mutableStateOf(false) }
    var bookingError by remember { mutableStateOf<String?>(null) }
    var tryOnSubmitting by remember { mutableStateOf(false) }
    var tryOnError by remember { mutableStateOf<String?>(null) }

    fun resetToLogin() {
        authUser = null
        authToken = null
        authError = null
        favorites.clear()
        bookingRecords = emptyList()
        pendingBooking = null
        userSettings = UserSettings("显白、法式、新中式", "试戴完成、预约提醒、活动通知", "手部照片仅用于试戴与订单关联")
        tryOnStatus = TryOnStatus()
        latestTryOnJob = null
        latestTryOnBitmap = null
        lastTryOnSourceFile = null
        bookingError = null
        tryOnError = null
        sharedPreferences.edit().remove(AppConfig.authTokenPreference).apply()
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

    fun launchTryOn(styleId: String, sourceFile: File, sourceChannel: String) {
        coroutineScope.launch {
            tryOnSubmitting = true
            tryOnError = null
            latestTryOnBitmap = null
            runCatching {
                lastTryOnSourceFile = sourceFile
                val upload = repository.uploadTryOnImage(sourceFile)
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
                latestTryOnJob = job
                tryOnStatus = TryOnStatus(jobId = job.id, stage = job.stage, progress = job.progress, status = job.status)
                go(Screen.TryOnProcessing(styleId, job.id))
            }.onFailure { error ->
                tryOnError = error.message ?: "创建试戴任务失败"
            }
            tryOnSubmitting = false
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
        val fetchedStyles = repository.styles().items.map { it.toUi() }
        val fetchedFavorites = repository.favorites().items.map { it.id }
        val fetchedStores = repository.stores().items.map { it.toUi() }
        val fetchedBookings = repository.bookings().items.map { it.toUi() }
        val fetchedSettings = repository.settings().toUi()

        authUser = me
        styleItems = fetchedStyles.ifEmpty { styles }
        favorites.clear()
        favorites.addAll(fetchedFavorites)
        storeItems = fetchedStores.ifEmpty { stores }
        bookingRecords = fetchedBookings
        userSettings = fetchedSettings
        hotKeywords = home.hotKeywords.ifEmpty { defaultHotKeywords }
        homeRecommended = home.recommended.map { it.toUi() }.ifEmpty { styleItems.take(2) }
        homeHot = home.hot.map { it.toUi() }.ifEmpty { styleItems }
        searchResults = styleItems
        if (selectedStoreId !in storeItems.map { it.id }) {
            selectedStoreId = storeItems.firstOrNull()?.id ?: stores.first().id
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
        is Screen.TryOnUpload -> "上传手部照片"
        is Screen.TryOnProcessing -> "手部识别中"
        is Screen.TryOnResult -> "试戴结果"
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
                            onClick = {
                                val firstStore = storeItems.firstOrNull() ?: stores.first()
                                selectedStoreId = firstStore.id
                                go(Screen.BookingForm(firstStore.id, styleDetailStyle.id))
                            },
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
                    initialEmail = "luna@nailmind.app",
                    initialPassword = "123456",
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
                    initialName = "Luna",
                    initialEmail = "luna@nailmind.app",
                    initialPassword = "123456",
                    showNameField = true,
                    loading = authLoading,
                    errorMessage = authError,
                    onPrimary = { name, email, password ->
                        coroutineScope.launch {
                            authLoading = true
                            authError = null
                            runCatching { repository.register(name = name.ifBlank { "Luna" }, email = email, password = password) }
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
                        onSearch = { go(Screen.Search) },
                        onStyleClick = { go(Screen.StyleDetail(it)) }
                    )
                    MainTab.Styles -> StylesScreen(
                        styles = styleItems,
                        onStyleClick = { go(Screen.StyleDetail(it)) }
                    )
                    MainTab.TryOn -> TryOnHubScreen(
                        favorites = styleItems.filter { favorites.contains(it.id) },
                        recommended = homeHot,
                        onHotPick = { go(Screen.TryOnUpload(it)) },
                        onFavoritePick = { go(Screen.TryOnUpload(it, fromFavorites = true)) }
                    )
                    MainTab.Booking -> BookingScreen(
                        stores = storeItems,
                        onStoreClick = { go(Screen.StoreDetail(it, null)) }
                    )
                    MainTab.Profile -> ProfileScreen(
                        user = authUser ?: AuthUser("Luna", "luna@nailmind.app"),
                        favoritesCount = favorites.size,
                        preferenceSummary = authUser?.preferences?.joinToString(" / ").orEmpty(),
                        onFavorites = { go(Screen.Favorites) },
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
                        onBook = {
                            val firstStore = storeItems.firstOrNull() ?: stores.first()
                            selectedStoreId = firstStore.id
                            go(Screen.BookingForm(firstStore.id, style.id))
                        }
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

                is Screen.TryOnUpload -> TryOnUploadScreen(
                    style = styleItems.firstOrNull { it.id == screen.styleId } ?: return@AnimatedContent,
                    fromFavorites = screen.fromFavorites,
                    loading = tryOnSubmitting,
                    errorMessage = tryOnError,
                    lastSourceFile = lastTryOnSourceFile,
                    onStartProcessing = { sourceFile, sourceChannel -> launchTryOn(screen.styleId, sourceFile, sourceChannel) }
                )

                is Screen.TryOnProcessing -> {
                    LaunchedEffect(screen.jobId) {
                        var consecutiveFailures = 0
                        while (true) {
                            val outcome = runCatching { repository.tryOnResult(screen.jobId) }
                            outcome.onSuccess { job ->
                                consecutiveFailures = 0
                                latestTryOnJob = job
                                tryOnStatus = TryOnStatus(
                                    jobId = job.id,
                                    stage = job.stage,
                                    progress = job.progress,
                                    status = job.status,
                                    errorMessage = job.errorMessage
                                )
                                if (job.status == "completed") {
                                    val imageBytes = runCatching { repository.tryOnResultImageBytes(screen.jobId) }.getOrNull()
                                    latestTryOnBitmap = imageBytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size) }
                                    stack.removeLast()
                                    stack.add(Screen.TryOnResult(screen.styleId, screen.jobId))
                                    return@LaunchedEffect
                                }
                                if (job.status == "failed") {
                                    return@LaunchedEffect
                                }
                            }.onFailure { error ->
                                consecutiveFailures += 1
                                tryOnStatus = tryOnStatus.copy(
                                    errorMessage = if (consecutiveFailures >= 3) {
                                        error.message ?: "试戴进度获取失败，请稍后重试"
                                    } else {
                                        null
                                    }
                                )
                            }
                            delay(1500)
                        }
                    }
                    TryOnProcessingScreen(
                        stage = tryOnStatus.stage,
                        progress = tryOnStatus.progress,
                        errorMessage = tryOnStatus.errorMessage,
                        onDone = { go(Screen.TryOnResult(screen.styleId, screen.jobId)) }
                    )
                }

                is Screen.TryOnResult -> TryOnResultScreen(
                    style = styleItems.firstOrNull { it.id == screen.styleId } ?: return@AnimatedContent,
                    favorite = favorites.contains(screen.styleId),
                    length = selectedLength,
                    shape = selectedShape,
                    resultStatus = latestTryOnJob?.status ?: "",
                    resultBitmap = latestTryOnBitmap,
                    onLengthChange = {
                        selectedLength = it
                        coroutineScope.launch {
                            runCatching {
                                repository.rerenderTryOn(
                                    screen.jobId,
                                    selectedLength = selectedLengthToApi(selectedLength),
                                    selectedShape = selectedShapeToApi(selectedShape)
                                )
                            }.onSuccess { rerendered ->
                                latestTryOnJob = rerendered
                                latestTryOnBitmap = null
                                tryOnStatus = TryOnStatus(jobId = rerendered.id, stage = rerendered.stage, progress = rerendered.progress, status = rerendered.status)
                                go(Screen.TryOnProcessing(screen.styleId, screen.jobId))
                            }
                        }
                    },
                    onShapeChange = {
                        selectedShape = it
                        coroutineScope.launch {
                            runCatching {
                                repository.rerenderTryOn(
                                    screen.jobId,
                                    selectedLength = selectedLengthToApi(selectedLength),
                                    selectedShape = selectedShapeToApi(selectedShape)
                                )
                            }.onSuccess { rerendered ->
                                latestTryOnJob = rerendered
                                latestTryOnBitmap = null
                                tryOnStatus = TryOnStatus(jobId = rerendered.id, stage = rerendered.stage, progress = rerendered.progress, status = rerendered.status)
                                go(Screen.TryOnProcessing(screen.styleId, screen.jobId))
                            }
                        }
                    },
                    onRetake = { go(Screen.TryOnUpload(screen.styleId)) },
                    onToggleFavorite = { toggleFavorite(screen.styleId) },
                    onBook = { go(Screen.BookingForm(selectedStoreId, screen.styleId)) }
                )

                Screen.Favorites -> FavoritesScreen(
                    styles = styleItems.filter { favorites.contains(it.id) },
                    onStyleClick = { go(Screen.StyleDetail(it)) },
                    onRetake = { go(Screen.TryOnUpload(it, true)) },
                    onBook = { go(Screen.BookingForm((storeItems.firstOrNull() ?: stores.first()).id, it)) }
                )

                Screen.BookingRecords -> BookingRecordsScreen(records = bookingRecords)

                is Screen.StoreDetail -> {
                    val store = storeItems.firstOrNull { it.id == screen.storeId } ?: return@AnimatedContent
                    StoreDetailScreen(
                        store = store,
                        onBook = {
                            selectedStoreId = store.id
                            go(Screen.BookingForm(store.id, screen.styleId ?: (styleItems.firstOrNull()?.id ?: styles.first().id)))
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

@Composable
private fun HomeScreen(
    recommended: List<NailStyle>,
    hot: List<NailStyle>,
    onSearch: () -> Unit,
    onStyleClick: (String) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "Nail Mind",
                            fontSize = 28.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "发现适合你的美甲风格",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.68f),
                            fontSize = 14.sp
                        )
                    }
                    IconButton(onClick = {}) {
                        Icon(
                            Icons.Rounded.NotificationsNone,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.size(24.dp)
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
                        MaterialTheme.colorScheme.outline.copy(alpha = 0.7f)
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
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
                            fontSize = 14.sp
                        )
                        Text(
                            text = "输入关键词",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.28f),
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }
        item {
            HomeSectionHeader(title = "推荐")
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                recommended.take(2).forEach { style ->
                    HomeFeaturedCard(
                        style = style,
                        modifier = Modifier.weight(1f),
                        onClick = { onStyleClick(style.id) }
                    )
                }
            }
        }
        item {
            HomeSectionHeader(title = "热门款式")
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                hot.take(3).forEach { style ->
                    HomeCompactCard(
                        style = style,
                        modifier = Modifier.weight(1f),
                        onClick = { onStyleClick(style.id) }
                    )
                }
            }
        }
    }
}

@Composable
private fun HomeSectionHeader(title: String) {
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
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "查看更多",
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
private fun StylesScreen(styles: List<NailStyle>, onStyleClick: (String) -> Unit) {
    val categories = listOf("全部", "推荐", "法式", "猫眼", "新中式", "显白", "短甲友好")
    val priceRanges = listOf("全部价格", "200以下", "200-260", "260以上")
    val nailTypes = listOf("全部甲型") + styles.map { it.nailType }.distinct()
    val skinTones = listOf("全部肤色", "黄一白", "自然肤色", "暖肤", "冷白皮")
    val scenes = listOf("全部场景", "通勤", "约会", "节日", "秋冬", "轻奢", "新中式")

    var selectedCategory by remember { mutableStateOf(categories.first()) }
    var showAdvanced by remember { mutableStateOf(false) }
    var selectedPriceRange by remember { mutableStateOf(priceRanges.first()) }
    var selectedNailType by remember { mutableStateOf(nailTypes.first()) }
    var selectedSkinTone by remember { mutableStateOf(skinTones.first()) }
    var selectedScene by remember { mutableStateOf(scenes.first()) }

    val filteredStyles = styles.filter { style ->
        val priceValue = style.price.filter { it.isDigit() }.toIntOrNull() ?: 0
        val matchCategory = when (selectedCategory) {
            "全部" -> true
            "短甲友好" -> style.vibe.contains("短") || style.tags.any { it.contains("短") }
            else -> style.name.contains(selectedCategory) ||
                style.vibe.contains(selectedCategory) ||
                style.tags.any { it.contains(selectedCategory) }
        }
        val matchPrice = when (selectedPriceRange) {
            "200以下" -> priceValue in 1..199
            "200-260" -> priceValue in 200..260
            "260以上" -> priceValue >= 261
            else -> true
        }
        val matchNailType = selectedNailType == "全部甲型" || style.nailType == selectedNailType
        val matchSkinTone = selectedSkinTone == "全部肤色" || style.skinTone.contains(selectedSkinTone)
        val matchScene = selectedScene == "全部场景" ||
            style.vibe.contains(selectedScene) ||
            style.tags.any { it.contains(selectedScene) } ||
            style.name.contains(selectedScene)

        matchCategory && matchPrice && matchNailType && matchSkinTone && matchScene
    }

    Row(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        Column(
            modifier = Modifier
                .width(92.dp)
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.96f))
                .padding(vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            categories.forEach { category ->
                Surface(
                    modifier = Modifier
                        .padding(horizontal = 10.dp)
                        .fillMaxWidth()
                        .clickable { selectedCategory = category },
                    color = if (selectedCategory == category) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else Color.Transparent,
                    shape = MaterialTheme.shapes.medium
                ) {
                    Column(
                        modifier = Modifier.padding(vertical = 12.dp, horizontal = 8.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = category,
                            color = if (selectedCategory == category) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f),
                            fontSize = 13.sp,
                            fontWeight = if (selectedCategory == category) FontWeight.Bold else FontWeight.Medium,
                            textAlign = TextAlign.Center
                        )
                    }
                }
            }
        }

        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("款式库", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                                Text(
                                    "当前分类: $selectedCategory",
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.64f),
                                    fontSize = 13.sp
                                )
                            }
                            OutlinedButton(onClick = { showAdvanced = !showAdvanced }) {
                                Text(if (showAdvanced) "收起筛选" else "高级筛选")
                            }
                        }
                        if (showAdvanced) {
                            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                LibraryFilterGroup("价格区间", priceRanges, selectedPriceRange) { selectedPriceRange = it }
                                LibraryFilterGroup("适合甲型", nailTypes, selectedNailType) { selectedNailType = it }
                                LibraryFilterGroup("适合肤色", skinTones, selectedSkinTone) { selectedSkinTone = it }
                                LibraryFilterGroup("场景风格", scenes, selectedScene) { selectedScene = it }
                            }
                        }
                    }
                }
            }

            item {
                Text(
                    "共 ${filteredStyles.size} 款",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f),
                    fontSize = 13.sp
                )
            }

            if (filteredStyles.isEmpty()) {
                item {
                    EmptyState("没有匹配款式", "换个分类，或在高级筛选里放宽价格、甲型和场景条件。")
                }
            } else {
                items(filteredStyles) { style ->
                    StyleGridRow(style = style, onClick = { onStyleClick(style.id) })
                }
            }
        }
    }
}

@Composable
private fun LibraryFilterGroup(
    title: String,
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            options.forEach { option ->
                FilterChip(
                    selected = selected == option,
                    onClick = { onSelect(option) },
                    label = { Text(option) }
                )
            }
        }
    }
}

@Composable
private fun TryOnHubScreen(
    favorites: List<NailStyle>,
    recommended: List<NailStyle>,
    onHotPick: (String) -> Unit,
    onFavoritePick: (String) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("AI 试戴入口", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("上传手部照片或直接拍照，系统会识别手型、甲床和肤色。", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        FilledIconButton(onClick = { recommended.firstOrNull()?.let { onHotPick(it.id) } }) {
                            Icon(Icons.Rounded.PhotoCamera, contentDescription = "拍照")
                        }
                        Button(onClick = { recommended.getOrNull(1)?.let { onHotPick(it.id) } ?: recommended.firstOrNull()?.let { onHotPick(it.id) } }) { Text("从热门款式开始") }
                    }
                }
            }
        }
        item { SectionHeader("从收藏中继续", "带出你上次试戴过的款式") }
        if (favorites.isEmpty()) {
            item { EmptyState("暂无收藏", "先去首页收藏喜欢的款式，再回来继续试戴。") }
        } else {
            items(favorites) { style ->
                CompactActionCard(
                    title = style.name,
                    subtitle = "再次上传手部照片，保留款式偏好",
                    primary = "再次试戴",
                    secondary = null,
                    onPrimary = { onFavoritePick(style.id) }
                )
            }
        }
        item { SectionHeader("系统推荐", "根据热度和适配手型") }
        item {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                items(recommended) { style ->
                    StyleCard(style = style, onClick = { onHotPick(style.id) }, modifier = Modifier.width(220.dp))
                }
            }
        }
    }
}

@Composable
private fun BookingScreen(stores: List<Store>, onStoreClick: (String) -> Unit) {
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
    preferenceSummary: String,
    onFavorites: () -> Unit,
    onRecords: () -> Unit,
    onSettings: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
            ) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(user.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(user.email, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                    Text("偏好: ${preferenceSummary.ifBlank { "显白法式 / 新中式 / 短甲友好" }}", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                }
            }
        }
        item {
            ProfileEntry("收藏", "已保存 $favoritesCount 个试戴相关款式", onFavorites)
        }
        item {
            ProfileEntry("预约记录", "查看到店时间、门店和订单状态", onRecords)
        }
        item {
            ProfileEntry("我的评价", "最近完成的服务评价与晒图", {})
        }
        item {
            ProfileEntry("设置", "通知、隐私与偏好设置", onSettings)
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
            DetailMetricCard(
                entries = listOf(
                    "参考价格" to style.price,
                    "适合甲长" to "短中",
                    "热度" to "1.2k"
                )
            )
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
            CompactActionCard(
                title = style.name,
                subtitle = if (fromFavorites) "来自我的收藏，试戴效果会一并保存。" else "当前选择的试戴款式。",
                primary = "开始识别",
                secondary = null,
                onPrimary = ::openCamera
            )
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
private fun TryOnProcessingScreen(stage: String, progress: Int, errorMessage: String?, onDone: () -> Unit) {
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
                Text("正在识别手部与甲床", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("当前阶段: ${stageLabel(stage)} · $progress%", textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.72f))
                errorMessage?.takeIf { it.isNotBlank() }?.let {
                    Text(it, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.error)
                }
                if (progress >= 100 && errorMessage.isNullOrBlank()) {
                    Button(onClick = onDone) { Text("查看试戴结果") }
                }
            }
        }
    }
}

@Composable
private fun TryOnResultScreen(
    style: NailStyle,
    favorite: Boolean,
    length: String,
    shape: String,
    resultStatus: String,
    resultBitmap: Bitmap?,
    onLengthChange: (String) -> Unit,
    onShapeChange: (String) -> Unit,
    onRetake: () -> Unit,
    onToggleFavorite: () -> Unit,
    onBook: () -> Unit
) {
    val lengths = listOf("自然短甲", "中短", "修长")
    val shapes = listOf("方圆", "椭圆", "杏仁")
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
            Text("任务状态: ${resultStatus.ifBlank { "completed" }}", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f))
        }
        item {
            SelectorGroup("长度切换", lengths, length, onLengthChange)
        }
        item {
            SelectorGroup("甲型切换", shapes, shape, onShapeChange)
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
                OutlinedButton(onClick = {}, modifier = Modifier.weight(1f)) { Text("保存图片") }
            }
        }
    }
}

@Composable
private fun FavoritesScreen(
    styles: List<NailStyle>,
    onStyleClick: (String) -> Unit,
    onRetake: (String) -> Unit,
    onBook: (String) -> Unit
) {
    if (styles.isEmpty()) {
        EmptyState("还没有收藏", "在款式详情页或试戴结果页收藏喜欢的款式。")
        return
    }
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
                            Text("保留试戴效果、甲型与甲长偏好", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f), fontSize = 13.sp)
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
                    Text("${store.distance} · ${store.priceBand} · 评分 ${store.score}")
                    TagRow(store.slots)
                }
            }
        }
        item {
            InfoGrid(
                listOf(
                    "营业时间" to "10:00 - 22:00",
                    "美甲师" to "6 位可预约",
                    "门店作品" to "480+",
                    "服务价格" to store.priceBand
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
    var name by remember { mutableStateOf("Luna") }
    var phone by remember { mutableStateOf("13800138000") }
    var note by remember { mutableStateOf("想保留原甲长度，希望颜色更浅。") }
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
        item { SectionHeader("确认订单", "请确认到店时间、门店和价格") }
        item {
            InfoGrid(
                listOf(
                    "款式" to booking.styleName,
                    "门店" to booking.storeName,
                    "时间" to booking.slot,
                    "预计价格" to booking.price
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

@Composable
private fun BookingRecordsScreen(records: List<BookingRecord>) {
    if (records.isEmpty()) {
        EmptyState("暂无预约记录", "完成预约后，这里会展示到店时间、门店和状态。")
        return
    }
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
            Text(style.price, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
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
                    Text("${store.distance} · ${store.priceBand}", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
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
                Canvas(modifier = Modifier.fillMaxSize()) {
                    drawRoundRect(
                        brush = Brush.verticalGradient(listOf(Color(0xFFFFF4F6), Color(0xFFF3E0E8))),
                        cornerRadius = androidx.compose.ui.geometry.CornerRadius(42f, 42f)
                    )
                    val xPositions = listOf(0.18f, 0.34f, 0.5f, 0.66f, 0.82f)
                    xPositions.forEachIndexed { index, x ->
                        drawLine(
                            color = Color(0xFFE0B3C3),
                            start = Offset(size.width * x, size.height * 0.22f),
                            end = Offset(size.width * x, size.height * 0.84f),
                            strokeWidth = size.width * 0.09f,
                            cap = StrokeCap.Round
                        )
                        drawLine(
                            brush = Brush.verticalGradient(style.colors),
                            start = Offset(size.width * x, size.height * 0.18f),
                            end = Offset(size.width * x, size.height * 0.4f),
                            strokeWidth = size.width * 0.11f,
                            cap = StrokeCap.Round
                        )
                        if (index < 4) {
                            drawCircle(
                                color = Color.White.copy(alpha = 0.22f),
                                radius = size.width * 0.05f,
                                center = Offset(size.width * x, size.height * 0.16f)
                            )
                        }
                    }
                }
            }
            Text(
                if (resultBitmap != null) "AI 试戴结果" else "AI 试戴预览",
                modifier = Modifier.align(Alignment.BottomCenter),
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.58f)
            )
        }
    }
}

@Composable
private fun SelectorGroup(
    title: String,
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.horizontalScroll(rememberScrollState())) {
            options.forEach { option ->
                FilterChip(selected = selected == option, onClick = { onSelect(option) }, label = { Text(option) })
            }
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
