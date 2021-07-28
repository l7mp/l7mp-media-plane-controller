# FILE *f;
# f = fopen("/proc/stat", "r");
# if (f) {
#     long user_now, nice_now, system_now, idle_now;
#     if (fscanf(f, "cpu  %li %li %li %li",
#                 &user_now, &nice_now, &system_now, &idle_now) == 4)
#     {
#         long used_now = user_now + nice_now + system_now;
#         long used_secs = used_now - used_last;
#         long idle_secs = idle_now - idle_last;
#         long total_secs = used_secs + idle_secs;
#         if (total_secs > 0 && used_last && idle_last)
#             g_atomic_int_set(&cpu_usage, (int) (used_secs
#                         * 10000 / total_secs));
#         used_last = used_now;
#         idle_last = idle_now;
#     }
#     else
#         ilog(LOG_WARN, "Failed to obtain CPU usage");
#     fclose(f);
# }
# }
import time

used_last, idle_last = 0, 0
while True:
    with open('/proc/stat', 'r') as f:
        cpu = f.readline()
        cpu_values = ' '.join(cpu.split())
        cpu_values = cpu_values.split(" ")
        user_now, nice_now, system_now, idle_now = int(cpu_values[1]), int(cpu_values[2]), int(cpu_values[3]), int(cpu_values[4])
        used_now = user_now + nice_now + system_now
        used_secs = used_now - used_last
        idle_secs = idle_now - idle_last
        total_secs = used_secs + idle_secs
        if (total_secs > 0 and used_last and idle_last):
            cpu = (used_secs * 10000 / total_secs) / 100
            print(f'{cpu:.2f}%')
        used_last = used_now
        idle_last = idle_now
    time.sleep(1)

