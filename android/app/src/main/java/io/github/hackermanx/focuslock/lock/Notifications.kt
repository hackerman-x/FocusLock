package io.github.hackermanx.focuslock.lock

import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import io.github.hackermanx.focuslock.MainActivity
import io.github.hackermanx.focuslock.R
import io.github.hackermanx.focuslock.core.Format

object Notifications {
    private const val CHANNEL_LOCK = "lock"
    private const val CHANNEL_EVENTS = "events"
    private const val ID_LOCK = 1
    private const val ID_EVENT = 2

    fun createChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_LOCK, ctx.getString(R.string.channel_lock), NotificationManager.IMPORTANCE_LOW),
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_EVENTS, ctx.getString(R.string.channel_events), NotificationManager.IMPORTANCE_DEFAULT),
        )
    }

    private fun openApp(ctx: Context) = PendingIntent.getActivity(
        ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    @SuppressLint("MissingPermission")
    private fun post(ctx: Context, id: Int, builder: NotificationCompat.Builder) {
        val nm = NotificationManagerCompat.from(ctx)
        if (!nm.areNotificationsEnabled()) return
        try {
            nm.notify(id, builder.build())
        } catch (_: SecurityException) {
        }
    }

    fun showLock(ctx: Context, endsAt: Long) = post(
        ctx, ID_LOCK,
        NotificationCompat.Builder(ctx, CHANNEL_LOCK)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(ctx.getString(R.string.notif_lock_title))
            .setContentText(ctx.getString(R.string.notif_lock_text, Format.end(endsAt)))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(openApp(ctx)),
    )

    fun cancelLock(ctx: Context) = NotificationManagerCompat.from(ctx).cancel(ID_LOCK)

    fun showEvent(ctx: Context, title: String, text: String) = post(
        ctx, ID_EVENT,
        NotificationCompat.Builder(ctx, CHANNEL_EVENTS)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(openApp(ctx)),
    )
}
