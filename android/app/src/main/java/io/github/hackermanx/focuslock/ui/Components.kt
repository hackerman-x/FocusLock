package io.github.hackermanx.focuslock.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldColors
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** A bordered panel with a small mono label, like the desktop app's cards. */
@Composable
fun Panel(label: String? = null, modifier: Modifier = Modifier, accent: Color? = null, content: @Composable ColumnScope.() -> Unit) {
    val c = FL.colors
    Column(
        modifier
            .fillMaxWidth()
            .background(c.surface, RoundedCornerShape(14.dp))
            .border(1.dp, accent ?: c.border, RoundedCornerShape(14.dp))
            .padding(horizontal = 18.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (label != null) Label(label, color = accent ?: c.inkFaint)
        content()
    }
}

@Composable
fun Label(text: String, color: Color = FL.colors.inkFaint) {
    Text(text.uppercase(), fontFamily = Mono, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 1.5.sp, color = color)
}

@Composable
fun Body(text: String, color: Color = FL.colors.inkDim, modifier: Modifier = Modifier) {
    Text(text, fontSize = 14.sp, lineHeight = 20.sp, color = color, modifier = modifier)
}

@Composable
fun Header(title: String, color: Color, subtitle: String? = null) {
    Column(Modifier.fillMaxWidth().padding(top = 20.dp, bottom = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        PixelText(title, color, maxPixel = 5.dp, shadow = FL.colors.surface2)
        if (subtitle != null) {
            Spacer(Modifier.height(10.dp))
            Text(subtitle.uppercase(), fontFamily = Mono, fontSize = 11.sp, letterSpacing = 2.sp, color = FL.colors.inkFaint)
        }
    }
}

@Composable
fun PinkButton(text: String, modifier: Modifier = Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    val c = FL.colors
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(10.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = c.pink, contentColor = c.onPink,
            disabledContainerColor = c.surface2, disabledContentColor = c.inkFaint,
        ),
    ) {
        Text(text.uppercase(), fontFamily = Mono, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
    }
}

@Composable
fun GhostButton(text: String, modifier: Modifier = Modifier, enabled: Boolean = true, color: Color = FL.colors.ink, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, FL.colors.border),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = color, disabledContentColor = FL.colors.inkFaint),
    ) {
        Text(text.uppercase(), fontFamily = Mono, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun CheckRow(label: String, checked: Boolean, sub: String? = null, onChange: (Boolean) -> Unit) {
    val c = FL.colors
    Row(
        Modifier.fillMaxWidth().clickable { onChange(!checked) }.padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onChange,
            colors = CheckboxDefaults.colors(checkedColor = c.pink, checkmarkColor = c.onPink, uncheckedColor = c.borderStrong),
        )
        Spacer(Modifier.width(4.dp))
        Column {
            Text(label, fontSize = 15.sp, color = c.ink)
            if (sub != null) Text(sub, fontSize = 12.sp, color = c.inkFaint)
        }
    }
}

@Composable
fun Chip(text: String, selected: Boolean, onClick: () -> Unit) {
    val c = FL.colors
    Text(
        text,
        fontFamily = Mono,
        fontSize = 13.sp,
        fontWeight = FontWeight.SemiBold,
        color = if (selected) c.onPink else c.ink,
        modifier = Modifier
            .background(if (selected) c.pink else c.surface2, RoundedCornerShape(8.dp))
            .border(1.dp, if (selected) c.pink else c.border, RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
    )
}

@Composable
fun StatusLine(ok: Boolean, text: String) {
    val c = FL.colors
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(if (ok) "●" else "○", color = if (ok) c.cyan else c.pink, fontSize = 14.sp)
        Spacer(Modifier.width(8.dp))
        Text(text, fontSize = 14.sp, color = if (ok) c.inkDim else c.ink)
    }
}

@Composable
fun fieldColors(): TextFieldColors {
    val c = FL.colors
    return OutlinedTextFieldDefaults.colors(
        focusedBorderColor = c.pink, unfocusedBorderColor = c.border,
        cursorColor = c.pink, focusedTextColor = c.ink, unfocusedTextColor = c.ink,
        focusedLabelColor = c.pink, unfocusedLabelColor = c.inkFaint,
        focusedContainerColor = c.surface2, unfocusedContainerColor = c.surface2,
    )
}
