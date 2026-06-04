package dev.mcserver.bridge;

import io.papermc.paper.event.player.AsyncChatEvent;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Statistic;
import org.bukkit.advancement.Advancement;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerAdvancementDoneEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;

public final class MinecraftLlmBridgePlugin extends JavaPlugin implements Listener {
    private HttpClient httpClient;
    private String backendUrl;
    private String bridgeToken;
    private String serverName;
    private boolean emitBlockEvents;
    private long playerSnapshotTicks;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();
        backendUrl = getConfig().getString("backend-url", "http://localhost:8000").replaceAll("/+$", "");
        bridgeToken = getConfig().getString("bridge-token", "change-this-bridge-token");
        serverName = getConfig().getString("server-name", "main");
        emitBlockEvents = getConfig().getBoolean("emit-block-events", false);
        playerSnapshotTicks = getConfig().getLong("player-snapshot-every-ticks", 100L);

        Bukkit.getPluginManager().registerEvents(this, this);

        long pollTicks = getConfig().getLong("poll-commands-every-ticks", 40L);
        long healthTicks = getConfig().getLong("health-event-every-ticks", 600L);
        Bukkit.getScheduler().runTaskTimerAsynchronously(this, this::pollCommands, pollTicks, pollTicks);
        Bukkit.getScheduler().runTaskTimerAsynchronously(this, this::sendHealthEvent, 100L, healthTicks);
        Bukkit.getScheduler().runTaskTimer(this, this::sendPlayerSnapshots, 120L, playerSnapshotTicks);

        getLogger().info("Minecraft LLM bridge enabled for backend " + backendUrl);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        postEvent("player_join", player, property("address", String.valueOf(player.getAddress())));
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        Component quitMessage = event.quitMessage();
        String reason = quitMessage == null ? "quit" : PlainTextComponentSerializer.plainText().serialize(quitMessage);
        postEvent("player_leave", event.getPlayer(), property("reason", reason));
    }

    @EventHandler
    public void onChat(AsyncChatEvent event) {
        String message = PlainTextComponentSerializer.plainText().serialize(event.message());
        postEvent("player_chat", event.getPlayer(), property("message", message));
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent event) {
        Player player = event.getEntity();
        String message = event.deathMessage() == null
            ? player.getName() + " died"
            : PlainTextComponentSerializer.plainText().serialize(event.deathMessage());
        postEvent("player_death", player, property("message", message));
    }

    @EventHandler
    public void onAdvancement(PlayerAdvancementDoneEvent event) {
        Advancement advancement = event.getAdvancement();
        postEvent("player_advancement", event.getPlayer(), property("key", advancement.getKey().toString()));
    }

    @EventHandler
    public void onBlockBreak(BlockBreakEvent event) {
        if (emitBlockEvents) {
            postEvent("block_break", event.getPlayer(), blockData(event.getBlock()));
        }
    }

    @EventHandler
    public void onBlockPlace(BlockPlaceEvent event) {
        if (emitBlockEvents) {
            postEvent("block_place", event.getPlayer(), blockData(event.getBlock()));
        }
    }

    private void postEvent(String type, Player player, String dataJson) {
        String payload = "{"
            + "\"type\":" + quote(type) + ","
            + "\"timestamp\":" + quote(Instant.now().toString()) + ","
            + "\"server\":" + quote(serverName) + ","
            + "\"player\":" + playerRef(player) + ","
            + "\"data\":" + dataJson
            + "}";
        sendPayload("/api/minecraft/events", payload);
    }

    private void sendHealthEvent() {
        String dataJson = "{"
            + "\"onlinePlayers\":" + Bukkit.getOnlinePlayers().size() + ","
            + "\"maxPlayers\":" + Bukkit.getMaxPlayers() + ","
            + "\"freeMemoryBytes\":" + Runtime.getRuntime().freeMemory() + ","
            + "\"maxMemoryBytes\":" + Runtime.getRuntime().maxMemory() + ","
            + "\"uptimeTicks\":" + Bukkit.getWorlds().stream().mapToLong(world -> world.getFullTime()).max().orElse(0L)
            + "}";
        String payload = "{"
            + "\"type\":\"server_health\","
            + "\"timestamp\":" + quote(Instant.now().toString()) + ","
            + "\"server\":" + quote(serverName) + ","
            + "\"player\":null,"
            + "\"data\":" + dataJson
            + "}";
        sendPayload("/api/minecraft/events", payload);
    }

    private void sendPlayerSnapshots() {
        for (Player player : Bukkit.getOnlinePlayers()) {
            postEvent("player_snapshot", player, playerSnapshotData(player));
        }
    }

    private void pollCommands() {
        String encodedServer = URLEncoder.encode(serverName, StandardCharsets.UTF_8);
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(backendUrl + "/api/minecraft/commands.txt?server=" + encodedServer))
            .version(HttpClient.Version.HTTP_1_1)
            .header("X-Bridge-Token", bridgeToken)
            .GET()
            .build();

        httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString())
            .thenAccept(response -> {
                if (response.statusCode() >= 300) {
                    getLogger().warning("Command poll failed: HTTP " + response.statusCode());
                    return;
                }
                for (String line : response.body().split("\\R")) {
                    if (!line.isBlank()) {
                        Bukkit.getScheduler().runTask(this, () -> executeCommandLine(line));
                    }
                }
            })
            .exceptionally(error -> {
                getLogger().warning("Command poll failed: " + error.getMessage());
                return null;
            });
    }

    private void executeCommandLine(String line) {
        String[] parts = line.split("\\t", 4);
        if (parts.length != 4) {
            getLogger().warning("Ignored malformed backend command line.");
            return;
        }

        String action = parts[1];
        String target = decode(parts[2]);
        String message = decode(parts[3]);

        switch (action) {
            case "minecraft_chat", "minecraft_broadcast" -> Bukkit.broadcast(Component.text(message));
            case "minecraft_whisper" -> {
                Player player = target.isBlank() ? null : Bukkit.getPlayerExact(target);
                if (player == null && !target.isBlank()) {
                    try {
                        player = Bukkit.getPlayer(UUID.fromString(target));
                    } catch (IllegalArgumentException ignored) {
                        player = null;
                    }
                }
                if (player != null) {
                    player.sendMessage(Component.text(message));
                } else {
                    Bukkit.broadcast(Component.text(message));
                }
            }
            default -> getLogger().warning("Ignored unsupported backend action: " + action);
        }
    }

    private void sendPayload(String path, String payload) {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(backendUrl + path))
            .version(HttpClient.Version.HTTP_1_1)
            .header("Content-Type", "application/json")
            .header("X-Bridge-Token", bridgeToken)
            .POST(HttpRequest.BodyPublishers.ofString(payload))
            .build();

        CompletableFuture.runAsync(() -> {
            try {
                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() >= 300) {
                    getLogger().warning("Backend rejected event: HTTP " + response.statusCode() + " " + response.body());
                }
            } catch (IOException e) {
                getLogger().warning("Backend event send failed: " + e.getMessage());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
    }

    private String playerRef(Player player) {
        return "{"
            + "\"uuid\":" + quote(player.getUniqueId().toString()) + ","
            + "\"name\":" + quote(player.getName()) + ","
            + "\"world\":" + quote(player.getWorld().getName()) + ","
            + "\"x\":" + player.getLocation().getBlockX() + ","
            + "\"y\":" + player.getLocation().getBlockY() + ","
            + "\"z\":" + player.getLocation().getBlockZ() + ","
            + "\"playTimeTicks\":" + player.getStatistic(Statistic.PLAY_ONE_MINUTE)
            + "}";
    }

    private String blockData(Block block) {
        return "{"
            + "\"material\":" + quote(block.getType().key().asString()) + ","
            + "\"world\":" + quote(block.getWorld().getName()) + ","
            + "\"x\":" + block.getX() + ","
            + "\"y\":" + block.getY() + ","
            + "\"z\":" + block.getZ()
            + "}";
    }

    private String playerSnapshotData(Player player) {
        String heldItem = player.getInventory().getItemInMainHand().getType().key().asString();
        String nearbyPlayers = player.getNearbyEntities(32, 32, 32).stream()
            .filter(entity -> entity instanceof Player)
            .map(entity -> quote(entity.getName()))
            .reduce((left, right) -> left + "," + right)
            .orElse("");

        return "{"
            + "\"world\":" + quote(player.getWorld().getName()) + ","
            + "\"x\":" + player.getLocation().getBlockX() + ","
            + "\"y\":" + player.getLocation().getBlockY() + ","
            + "\"z\":" + player.getLocation().getBlockZ() + ","
            + "\"health\":" + Math.round(player.getHealth()) + ","
            + "\"food\":" + player.getFoodLevel() + ","
            + "\"gameMode\":" + quote(player.getGameMode().name()) + ","
            + "\"heldItem\":" + quote(heldItem) + ","
            + "\"nearbyPlayers\":[" + nearbyPlayers + "],"
            + "\"playTimeTicks\":" + player.getStatistic(Statistic.PLAY_ONE_MINUTE)
            + "}";
    }

    private String property(String key, String value) {
        return "{" + quote(key) + ":" + quote(value) + "}";
    }

    private String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            switch (ch) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (ch < 0x20) {
                        out.append(String.format("\\u%04x", (int) ch));
                    } else {
                        out.append(ch);
                    }
                }
            }
        }
        return out.append('"').toString();
    }

    private String decode(String value) {
        return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
    }
}
