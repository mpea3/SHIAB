"""System Stats module - real-time CPU, RAM, disk, and network monitoring."""

from typing import Any

from app.modules.base import Module


class SystemStatsModule(Module):
    name = "system_stats"
    display_name = "System Stats"
    description = "Real-time CPU, RAM, disk, and network usage"
    icon = "&#128200;"  # 📈
    widget_template = "widgets/system_stats.html"
    widget_size = "medium"
    refresh_interval = 5

    async def get_data(self) -> dict[str, Any]:
        try:
            import psutil
        except ImportError:
            return {
                "error": True,
                "error_message": "psutil not installed. Run: pip install psutil",
            }

        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()

            temperatures: dict[str, float] = {}
            try:
                sensors = psutil.sensors_temperatures()
                if sensors:
                    for sensor_name, entries in sensors.items():
                        if entries:
                            temperatures[sensor_name] = round(entries[0].current, 1)
            except (AttributeError, Exception):
                pass

            load_avg = None
            try:
                load = psutil.getloadavg()
                load_avg = [round(x, 2) for x in load]
            except (AttributeError, Exception):
                pass

            # Per-CPU usage
            per_cpu = psutil.cpu_percent(percpu=True)

            return {
                "cpu_percent": round(cpu_percent, 1),
                "cpu_count": cpu_count,
                "cpu_freq_mhz": round(cpu_freq.current) if cpu_freq else None,
                "cpu_per_core": per_cpu,
                "ram_percent": round(ram.percent, 1),
                "ram_used_gb": round(ram.used / (1024 ** 3), 2),
                "ram_total_gb": round(ram.total / (1024 ** 3), 2),
                "ram_available_gb": round(ram.available / (1024 ** 3), 2),
                "disk_percent": round(disk.percent, 1),
                "disk_used_gb": round(disk.used / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2),
                "net_bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 1),
                "net_bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 1),
                "temperatures": temperatures,
                "load_avg": load_avg,
            }

        except Exception as e:
            return {"error": True, "error_message": f"System stats error: {e}"}

    def get_config_schema(self) -> dict[str, dict]:
        return {}
