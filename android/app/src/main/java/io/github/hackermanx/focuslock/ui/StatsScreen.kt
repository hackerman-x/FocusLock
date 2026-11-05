package io.github.hackermanx.focuslock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.hackermanx.focuslock.app
import io.github.hackermanx.focuslock.core.Clocks
import io.github.hackermanx.focuslock.core.Format
import io.github.hackermanx.focuslock.core.Streak
import io.github.hackermanx.focuslock.data.AppState
import io.github.hackermanx.focuslock.data.Attempt
import io.github.hackermanx.focuslock.data.HistoryEntry
import java.time.LocalDate
import java.time.ZoneId

@Composable
fun StatsScreen(st: AppState, now: Clocks) {
    val c = FL.colors
    val dao = LocalContext.current.app.db.dao()
    val startOfDay = remember(LocalDate.now()) {
        LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
    }
    val history by remember { dao.history() }.collectAsStateWithLifecycle(emptyList())
    val counts by remember { dao.attemptCounts() }.collectAsStateWithLifecycle(emptyList())
    val today by remember(startOfDay) { dao.attemptsSince(startOfDay) }.collectAsStateWithLifecycle(0)
    val allTime by remember { dao.attemptsSince(0) }.collectAsStateWithLifecycle(0)
    val focusMinutes = history.filter { it.kind == HistoryEntry.KIND_LOCK }
        .sumOf { ((it.endedAt ?: minOf(now.wall, it.plannedEnd)) - it.startedAt).coerceAtLeast(0) } / 60_000

    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Header("STATS", c.yellow) }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Tile("Streak", "${Streak.current(st.stats, LocalDate.now())}d", c.yellow, Modifier.weight(1f))
                Tile("Best", "${st.stats.longestStreak}d", c.pink, Modifier.weight(1f))
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Tile("Locks", "${st.stats.totalSessions}", c.cyan, Modifier.weight(1f))
                Tile("Focus time", Format.duration(focusMinutes), c.cyan, Modifier.weight(1f))
            }
        }
        item {
            Panel("Blocked attempts") {
                Text("$today today · $allTime in total", color = c.ink, fontSize = 15.sp)
                if (counts.isEmpty()) Body("Nothing yet. Every time a lock stops an app, a site or a settings screen, it shows up here.")
                counts.forEach { a ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(kindTag(a.kind), fontFamily = Mono, fontSize = 11.sp, color = c.inkFaint, modifier = Modifier.padding(end = 8.dp))
                        Text(a.label, color = c.ink, fontSize = 14.sp, modifier = Modifier.weight(1f))
                        Text("${a.count}", fontFamily = Mono, fontWeight = FontWeight.Bold, color = c.pink)
                    }
                }
            }
        }
        item { Label("History") }
        if (history.isEmpty()) item { Body("No locks yet.") }
        items(history, key = { it.id }) { HistoryRow(it) }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

private fun kindTag(kind: String) = when (kind) {
    Attempt.KIND_APP -> "APP"
    Attempt.KIND_SITE -> "SITE"
    Attempt.KIND_SETTINGS -> "SETTINGS"
    else -> "VPN"
}

@Composable
private fun Tile(label: String, value: String, color: Color, modifier: Modifier) {
    Panel(modifier = modifier) {
        Label(label)
        Text(value, fontFamily = Mono, fontWeight = FontWeight.Bold, fontSize = 24.sp, color = color)
    }
}

@Composable
private fun HistoryRow(e: HistoryEntry) {
    val c = FL.colors
    val (tag, color) = when (e.outcome) {
        HistoryEntry.OUTCOME_COMPLETED -> "COMPLETED" to c.cyan
        HistoryEntry.OUTCOME_ACTIVE -> "ACTIVE" to c.yellow
        HistoryEntry.OUTCOME_ENDED_EARLY -> "ENDED EARLY" to c.pink
        else -> "EMERGENCY" to c.pink
    }
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(Format.date(e.startedAt), color = c.ink, fontSize = 14.sp, modifier = Modifier.weight(1f))
            Text(
                tag, fontFamily = Mono, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = color,
                modifier = Modifier.background(c.surface2, RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 3.dp),
            )
        }
        Column {
            if (e.kind == HistoryEntry.KIND_EMERGENCY) {
                Body("Emergency switch used at ${Format.time(e.startedAt)}. The lock was due to end ${Format.end(e.plannedEnd)}.")
            } else {
                val planned = (e.plannedEnd - e.startedAt) / 60_000
                val apps = e.apps.split(',').count { it.isNotBlank() }
                val sites = e.sites.split(',').count { it.isNotBlank() }
                Body("${Format.time(e.startedAt)} · ${Format.duration(planned)} · $apps app(s), $sites site group(s)")
            }
            if (e.note.isNotBlank()) Body("“${e.note}”", color = c.ink)
        }
    }
}
