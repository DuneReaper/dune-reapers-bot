import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import aiosqlite
from datetime import datetime, timedelta


# Check if member has the "Shade" role
async def is_shaded(member: discord.Member) -> bool:
    return any(role.name == "Shade" for role in member.roles)


# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN_BOT_DC')

# Discord Intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

# Track voice sessions
voice_sessions = {}

TEXT_POINTS = 0.5

ABSENCE_REQUEST_CHANNEL_ID = 1359477781288845372
TICKET_CATEGORY_ID = 1360256145918263407
ADMIN_ROLE_ID = 1357822236039446748


@bot.event
async def on_ready():
    bot.add_view(WelcomePanelView4())
    print(f"{bot.user} is online.")
    await initialize_database()
    check_inactivity.start()

    # Register persistent views
    bot.add_view(CommandPanelView())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Slash command sync failed: {e}")


async def initialize_database():
    async with aiosqlite.connect('elo_database.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                elo INTEGER DEFAULT 1000,
                last_active TIMESTAMP,
                on_break INTEGER DEFAULT 0,
                break_start TIMESTAMP,
                break_end TIMESTAMP
            )
        ''')
        await db.commit()


async def update_user_activity(user_id):
    now = datetime.utcnow()
    async with aiosqlite.connect('elo_database.db') as db:
        await db.execute(
            '''
            INSERT INTO users (user_id, last_active)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_active = excluded.last_active
        ''', (str(user_id), now))
        await db.commit()


async def add_points(user_id, points):
    async with aiosqlite.connect('elo_database.db') as db:
        await db.execute(
            '''
            INSERT INTO users (user_id, elo, last_active)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET elo = elo + ?
        ''', (str(user_id), int(points), datetime.utcnow(), int(points)))
        await db.commit()


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if await is_shaded(message.author):
        return
    await add_points(message.author.id, TEXT_POINTS)
    await update_user_activity(message.author.id)
    await bot.process_commands(message)


@bot.event
async def on_ready():
    bot.add_view(WelcomePanelView4())
    print(f"{bot.user} is now online.")


@bot.command()
async def applypanel(ctx):
    view = WelcomePanelView4()
    await view.send(ctx)


@bot.event
async def on_voice_state_update(member, before, after):
    now = datetime.utcnow()
    user_id = str(member.id)
    if await is_shaded(member):
        return

    if before.channel is None and after.channel is not None:
        voice_sessions[user_id] = (after.channel.id, now)
    elif before.channel is not None and after.channel is None:
        if user_id in voice_sessions:
            _, start_time = voice_sessions.pop(user_id)
            minutes_spent = max(1, int(
                (now - start_time).total_seconds() / 300))
            channel = before.channel
            channel_name = ''.join(filter(
                str.isalpha, channel.name.lower())) if channel else ""

            if channel_name.startswith("Operation"):
                points_per_minute = 2.5
            elif channel_name.startswith("Roam"):
                points_per_minute = 1.0
            else:
                points_per_minute = 1.0

            points_earned = int(minutes_spent * points_per_minute)
            await add_points(user_id, points_earned)
            await update_user_activity(user_id)

            print(
                f"[VOCALELO] {member.display_name} earned {points_earned} points in {channel.name}"
            )


class CommandPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Management List",
                emoji="🧾",
                style=discord.ButtonStyle.link,
                url=
                "https://www.notion.so/1c413420e86080729416d9235414b4ae?v=1c413420e86081bca2e9000c20993c79&pvs=4"
            ))  # Replace with actual URL
        self.add_item(
            discord.ui.Button(
                label="Reapers Council",
                emoji="🛡️",
                style=discord.ButtonStyle.link,
                url=
                "https://discord.com/channels/YOUR_GUILD_ID/1355332092418068560"
            ))
        self.add_item(
            discord.ui.Button(
                label="Direction Logs",
                emoji="📊",
                style=discord.ButtonStyle.link,
                url=
                "https://discord.com/channels/YOUR_GUILD_ID/1355332142825210229"
            ))

    @discord.ui.button(label="📖 Info Panel",
                       style=discord.ButtonStyle.secondary,
                       custom_id="command_info")
    async def show_info(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        embed_info = discord.Embed(
            title=":tools: Officer Command Panel – How It Works",
            description=
            "Welcome to the core of our guild’s operations.\nIf you're reading this, you’ve earned our trust.\nHere’s how to use the tools available to guide the guild efficiently.",
            color=discord.Color.dark_gray())
        embed_info.add_field(name=":gear: PANEL OVERVIEW",
                             value="\u200b",
                             inline=False)
        embed_info.add_field(
            name=":link: Player Management List",
            value=
            "> Opens our internal Notion tracker. Every member is manually listed.\n- Track member status (:green_circle: active / :red_circle: inactive)\n- Note timezones for ops planning\n- Monitor warnings (:warning: max 3)\n- Flag or promote based on trust, behavior & contribution\n\n➡ Add new recruits as soon as they’re accepted\n➡ Update when someone disappears or excels",
            inline=False)
        embed_info.add_field(
            name=":busts_in_silhouette: Reapers Council",
            value=
            "> Officer-only channel. For votes, discussions, and inner-circle coordination.\n- Handle promotions / removals\n- Share critical updates\n- Plan internal strategy\n- Keep it respectful, strategic & efficient",
            inline=False)
        embed_info.add_field(
            name=":scroll: Direction Logs",
            value=
            "> Guild-wide strategic vision.\n\n- Long-term goals\n- PvP strategy outlines\n- Positioning in wars / alliances / territory / economy\n- Macro decisions that guide the guild’s direction\n\n**You’re free to lead your squad your way.\nBut everything must align with this vision.**",
            inline=False)
        embed_info.add_field(
            name=":information_source: Information",
            value=
            "> Hub for templates, resources, and useful tools.\n\n- Links (Notion, Google Forms, Discord utilities)\n- Templates for welcoming, promotions, etc.\n- Shared officer materials",
            inline=False)
        embed_info.add_field(
            name=":compass: YOUR ROLE AS AN OFFICER",
            value=
            "You are **not** a boss.\nYou are a **coordinator**, a **guardian**, a **Reaper**.\n\n- Lead your squad how you want just stay aligned.\n- Promote through action, not ego.\n- Build trust, not noise.\n- We don’t carry the guild. We hold the line. Together.\n\n:checkered_flag: **Your mission:**\n- Spot future Cloaked members\n- Sharpen the unit\n- Support the grind\n- Remove the dead weight\n- Zero drama. Maximum loyalty.\n\n**Silent. Loyal. Lethal.**",
            inline=False)
        await interaction.response.send_message(embed=embed_info,
                                                ephemeral=True)


@bot.command()
@commands.has_permissions(administrator=True)
async def commandpanel(ctx):
    embed = discord.Embed(title="**Command Panel**",
                          description="Choose your path",
                          color=discord.Color.dark_gold())
    embed.add_field(name="\n | Player Management List",
                    value="View and manage players in the guild.",
                    inline=False)
    embed.add_field(name="\n | Reapers Council",
                    value="Access council decisions and notes.",
                    inline=False)
    embed.add_field(name="\n | Direction Logs",
                    value="See logs of leadership actions.",
                    inline=False)
    embed.add_field(
        name="\n | Information",
        value="All internal documents, standards and announcements.",
        inline=False)
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/CHANNEL_ID/IMAGE_ID.png"
    )  # Replace this URL
    await ctx.send(embed=embed, view=CommandPanelView())


class WelcomePanelView1(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(color=0x393A41)
        embed.set_image(url="https://i.ibb.co/kGWvdgq/text1.png")
        await ctx.send(embed=embed, view=self)


class WelcomePanelView2(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(
            description=
            "### Diplomacy\nView all active Allies, Contracts\n or report in as an Emmisary.‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ",
            color=0x393A41)
        embed.set_thumbnail(url="https://i.ibb.co/gMZVhg8T/alliances.png")
        await ctx.send(embed=embed, view=self)


class WelcomePanelView3(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(
            description=
            "### **About us**\nAn overview of the Dune Reapers:\nour values, goals, and inner structure.‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎  ‎ ‎  ‎ ‎",
            color=0x393A41)
        embed.set_thumbnail(url="https://i.ibb.co/8D3fKfYs/information.png")
        await ctx.send(embed=embed, view=self)


class ApplicationModal(discord.ui.Modal, title="Dune Reapers Application"):

    def __init__(self):
        super().__init__()
        self.steam = discord.ui.TextInput(
            label="Steam Profile URL",
            placeholder="Please provide a direct link to your Steam profile.",
            style=discord.TextStyle.paragraph)
        self.WhyDR = discord.ui.TextInput(
            label="Why Dune Reapers?",
            placeholder=
            "What interests you about joining Dune Reapers? Tell us what drew you to our guild.",
            style=discord.TextStyle.paragraph)
        self.Availability = discord.ui.TextInput(
            label="Availability & Timezone:",
            placeholder=
            "What days and hours are you typically available to play? Please also include your timezone.",
            style=discord.TextStyle.paragraph)
        self.Background = discord.ui.TextInput(
            label="Gaming Background:",
            placeholder=
            "Top games played (with hours)? Any competitive, tournaments or clan experience?",
            style=discord.TextStyle.paragraph)
        self.Else = discord.ui.TextInput(
            label="Anything Else?",
            placeholder="Anything you'd like to add? (Optional)",
            required=False,
            style=discord.TextStyle.paragraph)

        self.add_item(self.steam)
        self.add_item(self.WhyDR)
        self.add_item(self.Availability)
        self.add_item(self.Background)
        self.add_item(self.Else)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(1360256145918263407)

        if category is None:
            await interaction.response.send_message(
                "❌ Error: The application category channel was not found. Please contact an administrator.",
                ephemeral=True)
            return

        # Check existing application
        for channel in category.text_channels:
            if channel.name == f"application-{interaction.user.name.lower()}":
                await interaction.response.send_message(
                    "⚠️ You already have an open application.", ephemeral=True)
                return

        overwrites = {
            guild.default_role:
            discord.PermissionOverwrite(view_channel=False),
            interaction.user:
            discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        admin_role = discord.utils.get(guild.roles, name="Admin")
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"application︱{interaction.user.name.lower()}",
            overwrites=overwrites,
            category=category)

        # Send first image
        await channel.send(
            content="https://i.ibb.co/jv7bZPH4/nog-meer-naar-l.png")

        # Send second image inside an embed
        image_embed = discord.Embed(color=0x393A41)
        image_embed.set_image(
            url="https://i.ibb.co/Z1tBKjDb/application-received17.png")
        await channel.send(embed=image_embed)

        description = (
            f" ## {interaction.user.mention.upper()}\n ## WISHES TO JOIN OUR RANKS!\n\n"
            f"1. **Steam Profile URL:**\n   > Answer: {self.steam.value}\n\n"
            f"2. **Why Dune Reapers?:**\n   > Answer: {self.WhyDR.value}\n\n"
            f"3. **Availability & Timezone:**\n   > Answer: {self.Availability.value}\n\n"
            f"4. **Gaming Background:**\n   > Answer: {self.Background.value}\n\n"
            f"5. **Anything Else?:**\n   > Answer: {self.Else.value or 'N/A'}\n\n"
            f" ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎‎  ‎ ‎ ‎ ‎‎ ‎ ‎ ‎‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎‎ ‎  ‎ ‎ ‎ ‎")

        embed = discord.Embed(description=description, color=0x393A41)
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Application created: {channel.mention}", ephemeral=True)


class WelcomePanelView4(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(
            description=
            "### Apply to Join\nFill the form. This is **mandatory** to join.‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎",
            color=0x393A41)
        embed.set_thumbnail(url="https://i.ibb.co/XkdmcVjV/apllymetscroll.png")
        await ctx.send(embed=embed, view=self)

    @discord.ui.button(label="Diplomacy",
                       style=discord.ButtonStyle.secondary,
                       row=0,
                       custom_id="alliances")
    async def show_alliances(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        await interaction.response.send_message(
            "Check <#1361059575654252647> for Diplomacy details.",
            ephemeral=True)

    @discord.ui.button(label="About us",
                       style=discord.ButtonStyle.secondary,
                       row=0,
                       custom_id="who_we_are")
    async def show_who_we_are(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        await interaction.response.send_message(
            "Read about us in <#1354238210485518407>.", ephemeral=True)

    @discord.ui.button(label="Apply to Join",
                       style=discord.ButtonStyle.success,
                       row=0,
                       custom_id="apply_button")
    async def apply_to_join(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal())


class AbsenceModal(discord.ui.Modal, title="Absence Request"):
    start_date = discord.ui.TextInput(label="Start Date (DD-MM-YYYY)",
                                      placeholder="09-04-2025")
    end_date = discord.ui.TextInput(label="End Date (DD-MM-YYYY)",
                                    placeholder="16-04-2025")
    reason = discord.ui.TextInput(label="Reason",
                                  placeholder="Note or justification...",
                                  style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            break_start = datetime.strptime(self.start_date.value, '%d-%m-%Y')
            break_end = datetime.strptime(self.end_date.value, '%d-%m-%Y')
        except ValueError:
            await interaction.response.send_message(
                "Invalid format. Use DD-MM-YYYY.", ephemeral=True)
            return

        if break_start >= break_end:
            await interaction.response.send_message(
                "Start date must be before end date.", ephemeral=True)
            return

        async with aiosqlite.connect('elo_database.db') as db:
            await db.execute(
                '''
                INSERT INTO users (user_id, on_break, break_start, break_end)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET on_break = 1, break_start = ?, break_end = ?
            ''', (str(interaction.user.id), break_start, break_end,
                  break_start, break_end))
            await db.commit()

        await interaction.response.send_message(
            "Your absence request has been submitted. An admin will assign the `Shade` role.",
            ephemeral=True)

        channel = bot.get_channel(ABSENCE_REQUEST_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="👻 New Absence Request",
                description=f"**From:** {interaction.user.mention}",
                color=discord.Color.dark_purple())
            embed.add_field(name="Reason",
                            value=self.reason.value,
                            inline=False)
            embed.add_field(
                name="Period",
                value=
                f"From **{self.start_date.value}** to **{self.end_date.value}**",
                inline=False)
            await channel.send(embed=embed)


class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="❌ Close Ticket",
                       style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction,
                    button: discord.ui.Button):
        await interaction.channel.delete()


@bot.tree.command(name="away", description="Request an absence period")
async def away_slash_command(interaction: discord.Interaction):
    await interaction.response.send_modal(AbsenceModal())


...


class AbsencePanelView1(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(color=0x393A41)
        embed.set_image(url="https://i.ibb.co/kGWvdgq/text1.png")
        await ctx.send(embed=embed, view=self)


class AbsencePanelView2(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(
            description=
            "### 📡 Operation Protocol\nGuild behavior, coordination expectations, and absence justification.",
            color=0x393A41)
        embed.set_image(url="https://i.ibb.co/jZV2G2M/text2.png")
        await ctx.send(embed=embed, view=self)


class AbsencePanelView3(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(
            description=
            "### 🎫 Ticket Support\nFor important topics only. Suggestion, content creation, or guild help.",
            color=0x393A41)
        embed.set_image(url="https://i.ibb.co/BV6nvnm/text3.png")
        await ctx.send(embed=embed, view=self)


# Panel Part 1
@bot.command()
@commands.has_permissions(administrator=True)
async def AbsencePanelView1(ctx):
    await ctx.send("https://i.ibb.co/PZ3qCqyt/text8.png")


# Panel Part 2
@bot.command()
@commands.has_permissions(administrator=True)
async def AbsencePanelView2(ctx):
    embed = discord.Embed(
        title="🛡️ Dune Reapers - Absence Panel",
        description="Guidance for managing your activity within the guild.",
        color=0x393A41)
    embed.add_field(
        name="Why Submit Absence?",
        value="Avoid automatic ELO decay and maintain your standing.",
        inline=False)
    embed.add_field(
        name="When to Submit",
        value="If you're inactive for more than 48h. Use the form below.",
        inline=False)
    embed.set_footer(text="Discipline is what sets Reapers apart.")
    await ctx.send(embed=embed)


# Panel Part 3
@bot.command()
@commands.has_permissions(administrator=True)
async def AbsencePanelView3(ctx):
    embed = discord.Embed(
        title="📡 Operation Protocol",
        description=
        "A Reaper follows structure. Here’s how we act during guild missions.",
        color=0x393A41)
    embed.add_field(
        name="Join Voice",
        value=
        "Operations are voice-led. Join the designated voice channel and be ready.",
        inline=False)
    embed.add_field(
        name="Follow Orders",
        value="Leaders give short and clear commands. Execute without delay.",
        inline=False)
    embed.add_field(
        name="Comms Discipline",
        value="No chatter during fights. Prioritize clarity and awareness.",
        inline=False)
    embed.set_footer(text="Efficiency wins wars.")
    await ctx.send(embed=embed)


# Panel Part 4
@bot.command()
@commands.has_permissions(administrator=True)
async def AbsencePanelView4(ctx):
    view = ReapersPanelView()
    await view.send(ctx)


# Reapers Control Panel with all interactions
class ReapersPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def send(self, ctx):
        embed = discord.Embed(title="🛡️ Dune Reapers - Activity Panel",
                              description="Choose your action below:",
                              color=0x393A41)
        embed.add_field(
            name="📡 Operation Protocol",
            value="View behavior rules and voice etiquette during operations.",
            inline=False)
        embed.add_field(
            name="🎫 Open Ticket",
            value="Ask for help, propose improvements or suggestions.",
            inline=False)
        embed.add_field(
            name="📆 Submit Absence",
            value=
            "Declare an absence with reason and dates. Shade role will be assigned manually.",
            inline=False)
        embed.set_footer(text="Stay sharp. Reapers are built, not born.")
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/CHANNEL_ID/IMAGE_ID.png"
        )  # Replace with your image URL
        await ctx.send(embed=embed, view=self)

    @discord.ui.button(label="📡 Operation Protocol",
                       style=discord.ButtonStyle.secondary,
                       custom_id="ops_protocol")
    async def show_ops_info(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await absencepanel3(interaction)

    @discord.ui.button(label="🎫 Open Ticket",
                       style=discord.ButtonStyle.secondary,
                       custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        for channel in category.text_channels:
            if channel.name == f"ticket-{interaction.user.name.lower()}":
                await interaction.response.send_message(
                    "You already have an open ticket! Please close it before opening a new one.",
                    ephemeral=True)
                return

        overwrites = {
            guild.default_role:
            discord.PermissionOverwrite(read_messages=False),
            interaction.user:
            discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites,
            category=category)

        await ticket_channel.send(view=CloseTicketView())

        embed = discord.Embed(
            title="📬 New Ticket Opened",
            description=
            f"**Welcome {interaction.user.mention}** <@&{ADMIN_ROLE_ID}>",
            color=discord.Color.dark_teal())
        embed.add_field(
            name="We handle",
            value=
            "- 💡 Suggestions & improvements\n- 📎 Sharing tools or strategies\n- 🎥 Content or recruitment ideas\n- 🧠 Anything smart that improves the guild",
            inline=False)
        embed.add_field(
            name="Reminder",
            value=
            "Respect the time of the team. Don’t open tickets for random questions or complaints, bring value.\n\n**Reapers don’t whine. They bring solutions.**",
            inline=False)
        await ticket_channel.send(embed=embed)
        await interaction.response.send_message(
            f"Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True)

    @discord.ui.button(label="📆 Submit Absence",
                       style=discord.ButtonStyle.danger,
                       custom_id="submit_absence")
    async def open_modal(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        await interaction.response.send_modal(AbsenceModal())


@bot.command(name='back')
async def end_absence(ctx):
    async with aiosqlite.connect('elo_database.db') as db:
        await db.execute(
            '''
            UPDATE users SET on_break = 0, break_start = NULL, break_end = NULL WHERE user_id = ?
        ''', (str(ctx.author.id), ))
        await db.commit()
    await ctx.send('Welcome back among us Reaper!.')


@tasks.loop(hours=24)
async def check_inactivity():
    now = datetime.utcnow()
    async with aiosqlite.connect('elo_database.db') as db:
        async with db.execute(
                'SELECT user_id, elo, last_active, on_break FROM users'
        ) as cursor:
            async for user_id, elo, last_active, on_break in cursor:
                if on_break:
                    continue
                if last_active:
                    days_inactive = (now -
                                     datetime.fromisoformat(last_active)).days
                    if days_inactive > 2:
                        loss = int(100 * (1.5**(days_inactive - 1)))
                        new_elo = max(0, elo - loss)
                        await db.execute(
                            'UPDATE users SET elo = ?, last_active = ? WHERE user_id = ?',
                            (new_elo, now, user_id))
        await db.commit()


@bot.command(name='elo')
@commands.has_permissions(administrator=True)
async def check_elo(ctx):
    user_id = str(ctx.author.id)
    async with aiosqlite.connect('elo_database.db') as db:
        async with db.execute('SELECT elo FROM users WHERE user_id = ?',
                              (user_id, )) as cursor:
            row = await cursor.fetchone()
            if row:
                await ctx.send(
                    f"🏆 {ctx.author.mention}, your current ELO is **{row[0]}**."
                )
            else:
                await ctx.send(
                    "You don't have an ELO yet. Start chatting or joining voice channels!"
                )


@bot.command(name="onbreak")
@commands.has_permissions(administrator=True)
async def show_on_break(ctx):
    async with aiosqlite.connect('elo_database.db') as db:
        async with db.execute(
                'SELECT user_id, break_start, break_end FROM users WHERE on_break = 1'
        ) as cursor:
            rows = await cursor.fetchall()
    if not rows:
        await ctx.send("No members are currently on break.")
    else:
        msg = "**Members that are currently on break:**\n"
        for user_id, start, end in rows:
            user = await bot.fetch_user(int(user_id))
            msg += f"• {user.name} – from {start} to {end}\n"
        await ctx.send(msg)


@bot.command()
@commands.has_permissions(administrator=True)
async def welcomepanel1(ctx):
    await ctx.send("https://i.ibb.co/PZ3qCqyt/text8.png")


@bot.command()
@commands.has_permissions(administrator=True)
async def welcomepanel2(ctx):
    view = WelcomePanelView2()
    await view.send(ctx)


@bot.command()
@commands.has_permissions(administrator=True)
async def welcomepanel3(ctx):
    view = WelcomePanelView3()
    await view.send(ctx)


@bot.command()
@commands.has_permissions(administrator=True)
async def welcomepanel4(ctx):
    view = WelcomePanelView4()
    await view.send(ctx)


@bot.command()
@commands.has_permissions(administrator=True)
async def absencepanel1(ctx):
    await ctx.send("https://i.ibb.co/PZ3qCqyt/text8.png")


@bot.command()
@commands.has_permissions(administrator=True)
async def absencepanel2(ctx):
    view = AbsencePanelView2()
    await view.send(ctx)


@bot.command()
@commands.has_permissions(administrator=True)
async def absencepanel3(ctx):
    view = AbsencePanelView3()
    await view.send(ctx)


@bot.command()
@commands.has_permissions(administrator=True)
async def absencepanel4(ctx):
    view = AbsencePanelView4()
    await view.send(ctx)


@bot.command()
@commands.has_permissions(administrator=True)
async def showimage(ctx):
    await ctx.send("https://i.ibb.co/jv7bZPH4/nog-meer-naar-l.png")


@bot.command()
@commands.has_permissions(administrator=True)
async def showimage1(ctx):
    await ctx.send(
        "https://images-ext-1.discordapp.net/external/1gdXDIMiErw6HdSphvEAt7XZMknPUWg8A9uIQzFgcvU/https/i.ibb.co/GQ6nM8dv/Vector-118.png?format=webp&quality=lossless&width=1860&height=325"
    )


bot.run(TOKEN)
