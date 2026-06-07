import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) {
        file.inputStream().use { load(it) }
    }
}

fun stringProperty(name: String, defaultValue: String): String {
    return (localProperties.getProperty(name) ?: providers.gradleProperty(name).orNull ?: System.getenv(name) ?: defaultValue)
}

fun intProperty(name: String, defaultValue: Int): Int {
    return stringProperty(name, defaultValue.toString()).toIntOrNull() ?: defaultValue
}

val releaseStoreFile = stringProperty("NAILMIND_RELEASE_STORE_FILE", "")
val hasReleaseSigning = releaseStoreFile.isNotBlank()

if (!hasReleaseSigning) {
    logger.warn("NAILMIND release signing config not found, falling back to debug signing for release builds.")
}

android {
    namespace = "com.nailmind.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.nailmind.app"
        minSdk = 26
        targetSdk = 35
        versionCode = intProperty("NAILMIND_VERSION_CODE", 2)
        versionName = stringProperty("NAILMIND_VERSION_NAME", "1.0.1")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }

        buildConfigField("String", "API_BASE_URL", "\"${stringProperty("NAILMIND_API_BASE_URL", "http://10.0.2.2:8080/")}\"")
        buildConfigField("String", "API_MEDIA_BASE_URL", "\"${stringProperty("NAILMIND_API_MEDIA_BASE_URL", stringProperty("NAILMIND_API_BASE_URL", "http://10.0.2.2:8080/"))}\"")
        buildConfigField("long", "API_TIMEOUT_SECONDS", stringProperty("NAILMIND_API_TIMEOUT_SECONDS", "20"))
    }

    signingConfigs {
        create("release") {
            if (hasReleaseSigning) {
                storeFile = rootProject.file(releaseStoreFile)
                storePassword = stringProperty("NAILMIND_RELEASE_STORE_PASSWORD", "")
                keyAlias = stringProperty("NAILMIND_RELEASE_KEY_ALIAS", "")
                keyPassword = stringProperty("NAILMIND_RELEASE_KEY_PASSWORD", "")
            }
        }
    }

    buildTypes {
        release {
            isDebuggable = false
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = if (hasReleaseSigning) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.compose.ui:ui:1.7.8")
    implementation("androidx.compose.ui:ui-graphics:1.7.8")
    implementation("androidx.compose.ui:ui-tooling-preview:1.7.8")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("androidx.compose.foundation:foundation:1.7.8")
    implementation("androidx.compose.material:material-icons-extended:1.7.8")
    implementation("androidx.compose.material:material-ripple:1.7.8")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.google.code.gson:gson:2.11.0")
    implementation("io.coil-kt:coil-compose:2.7.0")

    debugImplementation("androidx.compose.ui:ui-test-manifest:1.7.8")
}
