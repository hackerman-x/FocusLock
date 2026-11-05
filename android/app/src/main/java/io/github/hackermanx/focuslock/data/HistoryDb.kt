package io.github.hackermanx.focuslock.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

/** One lock, or one use of the emergency switch. */
@Entity(tableName = "history")
data class HistoryEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val kind: String,
    val startedAt: Long,
    val plannedEnd: Long,
    val endedAt: Long?,
    val outcome: String,
    /** Comma-separated package names. */
    val apps: String,
    /** Comma-separated site groups and domains. */
    val sites: String,
    val note: String,
) {
    companion object {
        const val KIND_LOCK = "lock"
        const val KIND_EMERGENCY = "emergency"
        const val OUTCOME_ACTIVE = "active"
        const val OUTCOME_COMPLETED = "completed"
        const val OUTCOME_ENDED_EARLY = "ended_early"
        const val OUTCOME_EMERGENCY = "emergency"
    }
}

/** Something the lock stopped: an app, a website, or a protected Settings screen. */
@Entity(tableName = "attempts")
data class Attempt(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val time: Long,
    val kind: String,
    val target: String,
    val label: String,
) {
    companion object {
        const val KIND_APP = "app"
        const val KIND_SITE = "site"
        const val KIND_SETTINGS = "settings"
        const val KIND_VPN = "vpn"
    }
}

data class AttemptCount(val kind: String, val label: String, val count: Int)

@Dao
interface HistoryDao {
    @Insert
    suspend fun insert(entry: HistoryEntry): Long

    @Query("UPDATE history SET outcome = :outcome, endedAt = :endedAt WHERE id = :id")
    suspend fun finish(id: Long, outcome: String, endedAt: Long)

    @Query("SELECT * FROM history ORDER BY startedAt DESC LIMIT 200")
    fun history(): Flow<List<HistoryEntry>>

    @Insert
    suspend fun insertAttempt(attempt: Attempt)

    @Query("SELECT kind, label, COUNT(*) AS count FROM attempts GROUP BY kind, target ORDER BY count DESC LIMIT 20")
    fun attemptCounts(): Flow<List<AttemptCount>>

    @Query("SELECT COUNT(*) FROM attempts WHERE time >= :since")
    fun attemptsSince(since: Long): Flow<Int>
}

@Database(entities = [HistoryEntry::class, Attempt::class], version = 1, exportSchema = false)
abstract class HistoryDb : RoomDatabase() {
    abstract fun dao(): HistoryDao

    companion object {
        fun open(context: Context): HistoryDb =
            Room.databaseBuilder(context, HistoryDb::class.java, "history.db").build()
    }
}
