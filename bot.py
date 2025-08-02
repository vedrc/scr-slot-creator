import main as p
import discord
from discord import app_commands
from discord.ext import commands
import os
import traceback
import asyncio
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class SlotCardView(discord.ui.View):
    def __init__(self, start, end, lst):
        super().__init__()
        self.start = start
        self.end = end
        self.list = lst

    async def update_message(self, msg, title, description, color, view=None):
        await msg.edit(embed=discord.Embed(title=title, description=description, color=color), view=view)

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.green)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        msg = await interaction.original_response()

        await self.update_message(msg, "Processing...", f"The bot is now creating slot cards between **{self.start}** and **{self.end}.** Please wait...", 0xeb842d)

        try:
            slots = await p.process(self.start, self.end, self.list)
            if not slots:
                slotmsg = "No slots were created as no training gaps are open."
            else:
                slotmsg = "The following slots have been created:\n\n" + "\n".join(slots) + "\n\nPlease manually **order the created slots.**"
            await self.update_message(msg, "Success!", slotmsg, 0x008000)
        except Exception:
            traceback.print_exc()
            await self.update_message(msg, "Something went wrong...", "Please make sure the dates inputted were correct. If so, please contact Ved.", 0xB31B1B)

    @discord.ui.button(label='No', style=discord.ButtonStyle.red)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        msg = await interaction.original_response()

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            await self.update_message(msg, "Start Date", "Please enter the **start date** for the slot using the **DD/MM/YY** format.", 0xeb842d)
            start_msg = await interaction.client.wait_for('message', check=check, timeout=60.0)
            self.start = start_msg.content.strip()
            await start_msg.delete()

            if not self.start:
                await self.update_message(msg, "Cancelled", "Empty message received. Please try the command again.", 0xB31B1B)
                return

            await self.update_message(msg, "End Date", f"**Start date:** {self.start}\nPlease enter the **end date** for the slot using the **DD/MM/YY** format.", 0xeb842d)
            end_msg = await interaction.client.wait_for('message', check=check, timeout=60.0)
            self.end = end_msg.content.strip()
            await end_msg.delete()

            if not self.end:
                await self.update_message(msg, "Cancelled", "Empty message received. Please try the command again.", 0xB31B1B)
                return

            await self.update_message(msg, "Processing...", "The bot is now creating slot cards. Please wait...", 0xeb842d)

            try:
                slots = await p.process(self.start, self.end, self.list)
                if not slots:
                    slotmsg = "No slots were created as no training gaps are open."
                else:
                    slotmsg = "The following slots have been created:\n\n" + "\n".join(slots) + "\n\nPlease manually **order the created slots.**"
                await self.update_message(msg, "Success!", slotmsg, 0x008000)
            except Exception:
                traceback.print_exc()
                await self.update_message(msg, "Something went wrong...", "Please make sure the dates inputted were correct. If so, please contact Ved.", 0xB31B1B)

        except asyncio.TimeoutError:
            await self.update_message(msg, "Cancelled", "You did not respond in time. Please rerun the command.", 0xB31B1B)

@tree.command(name="createslots", description="Creates slot cards for the designated scheduling window.", guild=discord.Object(id=691812653915439145))
async def createslots(interaction: discord.Interaction):
    start, end, lst = p.init()
    view = SlotCardView(start, end, lst)
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Scheduling Window",
            description=f"The bot will create slots between **{start}** - **{end}**. Is this correct?",
            color=0xeb842d
        ),
        view=view,
        ephemeral=True
    )

@client.event

async def on_ready():
    try:
        synced = await tree.sync(guild=discord.Object(id=691812653915439145))
        print(f"Synced {len(synced)} command(s) to test guild.")
    except Exception as e:
        print(f"Sync error: {e}")

client.run(DISCORD_TOKEN)

