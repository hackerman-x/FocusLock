plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

// Release signing comes from the environment (GitHub secrets in CI), so the
// keystore and its passwords never live in the repo.
val releaseKeystore: String? = System.getenv("FOCUSLOCK_KEYSTORE")

android {
    namespace = "io.github.hackermanx.focuslock"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.hackermanx.focuslock"
        minSdk = 26
        targetSdk = 35
        versionCode = System.getenv("FOCUSLOCK_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = System.getenv("FOCUSLOCK_VERSION")?.removePrefix("v") ?: "1.0.0"
    }

    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = System.getenv("FOCUSLOCK_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("FOCUSLOCK_KEY_ALIAS")
                keyPassword = System.getenv("FOCUSLOCK_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (releaseKeystore != null) signingConfig = signingConfigs.getByName("release")
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
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons)
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    implementation(libs.datastore.preferences)
    implementation(libs.kotlinx.coroutines.android)
    debugImplementation(libs.compose.ui.tooling)

    testImplementation(libs.junit)
}
