package io.github.hackermanx.focuslock.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.wrapContentWidth

/**
 * The desktop app's pixel title ('Press Start 2P' in the web UI), drawn from a
 * built-in 5x7 font so there's no font file to ship. Shrinks to fit the width.
 */
@Composable
fun PixelText(text: String, color: Color, modifier: Modifier = Modifier, maxPixel: Dp = 5.dp, shadow: Color? = null) {
    val glyphs = text.uppercase().map { GLYPHS[it] ?: BLANK }
    val cols = glyphs.size * 6 - 1
    BoxWithConstraints(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        val px = minOf(maxPixel, maxWidth / (cols + 1))
        Canvas(Modifier.wrapContentWidth().size(px * (cols + 1), px * 8)) {
            val p = px.toPx()
            val cell = Size(p + 0.5f, p + 0.5f)
            fun draw(dx: Float, dy: Float, c: Color) {
                glyphs.forEachIndexed { i, g ->
                    g.forEachIndexed { row, line ->
                        line.forEachIndexed { col, ch ->
                            if (ch == '#') drawRect(c, Offset((i * 6 + col) * p + dx, row * p + dy), cell)
                        }
                    }
                }
            }
            if (shadow != null) draw(p, p, shadow)
            draw(0f, 0f, color)
        }
    }
}

private val BLANK = List(7) { "     " }

private val GLYPHS: Map<Char, List<String>> = mapOf(
    'A' to listOf(" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    'B' to listOf("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    'C' to listOf(" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "),
    'D' to listOf("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    'E' to listOf("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    'F' to listOf("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    'G' to listOf(" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ####"),
    'H' to listOf("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    'I' to listOf(" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    'J' to listOf("  ###", "   # ", "   # ", "   # ", "#  # ", "#  # ", " ##  "),
    'K' to listOf("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    'L' to listOf("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    'M' to listOf("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    'N' to listOf("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    'O' to listOf(" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    'P' to listOf("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    'Q' to listOf(" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    'R' to listOf("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    'S' to listOf(" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    'T' to listOf("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    'U' to listOf("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    'V' to listOf("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    'W' to listOf("#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "),
    'X' to listOf("#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"),
    'Y' to listOf("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    'Z' to listOf("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    '0' to listOf(" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    '1' to listOf("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    '2' to listOf(" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"),
    '3' to listOf("#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "),
    '4' to listOf("   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "),
    '5' to listOf("#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "),
    '6' to listOf("  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "),
    '7' to listOf("#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "),
    '8' to listOf(" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "),
    '9' to listOf(" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "),
    ':' to listOf("     ", "  #  ", "  #  ", "     ", "  #  ", "  #  ", "     "),
    '!' to listOf("  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "),
    '.' to listOf("     ", "     ", "     ", "     ", "     ", "     ", "  #  "),
    '-' to listOf("     ", "     ", "     ", "#####", "     ", "     ", "     "),
)
