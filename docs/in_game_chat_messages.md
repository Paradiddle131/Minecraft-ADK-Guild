# In-Game Chat Messages Reference

This document lists all in-game chat messages sent by the bot, following the concise messaging pattern established in the refactoring.

## Movement Commands

| Function | Message | When Sent |
|----------|---------|-----------|
| `move_to_with_progress()` | `{distance:.0f} blocks left` | Every 5 seconds during movement |
| `move_to` (via tools) | `Arrived` | When movement completes successfully |

## Crafting Commands

| Function | Message | When Sent |
|----------|---------|-----------|
| `craft_item` (via tools) | `Crafting {count} {name}` | When starting to craft |
| `craft_item` (via tools) | `Crafted {count} {name}` | When crafting completes |

## General Commands

| Function | Message | When Sent |
|----------|---------|-----------|
| `send_chat()` | User-specified message | When agent uses send_chat tool |

## Message Guidelines

1. **Keep messages short** - Maximum 5-10 words
2. **Be informative** - Include key numbers (distance, count)
3. **Avoid redundancy** - Don't repeat information visible in UI
4. **Use present tense** - "Crafting" not "I am crafting"
5. **No punctuation** - Keep it minimal for chat readability

## Examples of Good vs Bad Messages

### Good (Concise)
- ✅ `10 blocks left`
- ✅ `Arrived`
- ✅ `Crafting 4 sticks`
- ✅ `Crafted 4 sticks`
- ✅ `Gathering oak_log`

### Bad (Too Verbose)
- ❌ `I am currently moving towards the destination, 10 blocks remaining`
- ❌ `Successfully arrived at the target destination!`
- ❌ `Starting the crafting process for 4 sticks...`
- ❌ `I have successfully crafted 4 sticks for you.`
- ❌ `Beginning to gather oak_log blocks now`