import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:permission_handler/permission_handler.dart';

import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// «Уведомления и фон» — экран самодиагностики и быстрых действий.
///
/// Зачем: на Xiaomi/HyperOS (и в меньшей мере Samsung/Honor) FCM режут
/// агрессивно. Пользователь должен явно разрешить автозапуск, отключить
/// оптимизацию батареи, проверить разрешение на уведомления. Тут это
/// собрано в один чеклист с прямыми кнопками + тестовый push.
class NotificationsHealthScreen extends ConsumerStatefulWidget {
  const NotificationsHealthScreen({super.key});

  @override
  ConsumerState<NotificationsHealthScreen> createState() =>
      _NotificationsHealthScreenState();
}

class _NotificationsHealthScreenState
    extends ConsumerState<NotificationsHealthScreen>
    with WidgetsBindingObserver {
  PermissionStatus? _notif;
  PermissionStatus? _battery;
  String? _vendor; // 'xiaomi' / 'samsung' / 'huawei' / null
  bool _testing = false;
  String? _testResult;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refreshAll();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // После возврата из системных настроек — обновляем статусы.
    if (state == AppLifecycleState.resumed) {
      _refreshAll();
    }
  }

  Future<void> _refreshAll() async {
    final notif = await Permission.notification.status;
    PermissionStatus? bat;
    if (Platform.isAndroid) {
      bat = await Permission.ignoreBatteryOptimizations.status;
    }
    String? vendor;
    if (Platform.isAndroid) {
      try {
        final info = await DeviceInfoPlugin().androidInfo;
        final manuf = info.manufacturer.toLowerCase();
        if (manuf.contains('xiaomi') ||
            manuf.contains('redmi') ||
            manuf.contains('poco')) {
          vendor = 'xiaomi';
        } else if (manuf.contains('samsung')) {
          vendor = 'samsung';
        } else if (manuf.contains('huawei') || manuf.contains('honor')) {
          vendor = 'huawei';
        } else if (manuf.contains('oppo') || manuf.contains('realme')) {
          vendor = 'oppo';
        } else if (manuf.contains('vivo')) {
          vendor = 'vivo';
        }
      } catch (_) {}
    }
    if (!mounted) return;
    setState(() {
      _notif = notif;
      _battery = bat;
      _vendor = vendor;
    });
  }

  Future<void> _requestNotification() async {
    HapticFeedback.lightImpact();
    final s = await Permission.notification.request();
    if (!mounted) return;
    setState(() => _notif = s);
    if (s.isPermanentlyDenied) {
      _toast('Открой системные настройки и включи уведомления вручную.');
      await openAppSettings();
    }
  }

  Future<void> _requestBattery() async {
    HapticFeedback.lightImpact();
    final s = await Permission.ignoreBatteryOptimizations.request();
    if (!mounted) return;
    setState(() => _battery = s);
  }

  Future<void> _openAppSettings() async {
    HapticFeedback.selectionClick();
    await openAppSettings();
  }

  Future<void> _sendTestPush() async {
    HapticFeedback.mediumImpact();
    setState(() {
      _testing = true;
      _testResult = null;
    });
    try {
      final dio = ref.read(dioProvider);
      final resp = await dio.post<Map<String, dynamic>>(
        '/push/test',
        data: {
          'title': 'Methodex',
          'body': 'Канал работает. Если ты это видишь — всё ок.',
        },
        options: Options(receiveTimeout: const Duration(seconds: 15)),
      );
      final sent = (resp.data?['sent'] as num?)?.toInt() ?? 0;
      final total = (resp.data?['total'] as num?)?.toInt() ?? 0;
      if (!mounted) return;
      setState(() {
        _testResult = sent == 0
            ? 'Сервер принял запрос, но FCM никуда не доставил. Возможно, токен устарел — попробуй выйти и войти заново.'
            : 'Отправлено на $sent из $total устройств. Жди уведомление в течение 30 секунд.';
      });
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      String msg;
      if (code == 404) {
        msg =
            'Сервер не видит твоих устройств. Проверь разрешение на уведомления выше — без него токен не регистрируется.';
      } else if (code == 503) {
        msg = 'На сервере не настроен FCM. Это починим со стороны бэка.';
      } else {
        msg = 'Сеть: ${e.message ?? code}';
      }
      if (mounted) setState(() => _testResult = msg);
    } catch (e) {
      if (mounted) setState(() => _testResult = '$e');
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        leading: IconButton(
          icon: const Icon(LucideIcons.chevronLeft),
          onPressed: () => context.pop(),
        ),
        title: Text('Уведомления и фон', style: t.textTheme.titleLarge),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          Text(
            'Если напоминания не приходят — пройдись по чеклисту. Особенно на Xiaomi/HyperOS: система по умолчанию режет фоновую работу всех приложений.',
            style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
          const SizedBox(height: 20),

          // 1. Notification permission
          _CheckTile(
            ok: _notif?.isGranted ?? false,
            title: 'Разрешение на уведомления',
            subtitle: _notif == null
                ? 'Проверяю…'
                : _notif!.isGranted
                    ? 'Разрешено'
                    : _notif!.isPermanentlyDenied
                        ? 'Заблокировано в системе. Включи вручную.'
                        : 'Не разрешено',
            actionLabel: _notif?.isGranted == true ? null : 'Включить',
            onAction: _requestNotification,
          ),

          // 2. Battery (Android only)
          if (Platform.isAndroid)
            _CheckTile(
              ok: _battery?.isGranted ?? false,
              title: 'Без ограничений батареи',
              subtitle: _battery == null
                  ? 'Проверяю…'
                  : _battery!.isGranted
                      ? 'Система не убивает приложение в фоне'
                      : 'Система может выгружать приложение и блокировать пуши',
              actionLabel: _battery?.isGranted == true ? null : 'Запросить',
              onAction: _requestBattery,
            ),

          const SizedBox(height: 8),

          // 3. Vendor-specific guide
          if (_vendor == 'xiaomi') const _XiaomiGuide(),
          if (_vendor == 'samsung') const _SamsungGuide(),
          if (_vendor == 'huawei') const _HuaweiGuide(),
          if (_vendor == 'oppo' || _vendor == 'vivo') const _OppoVivoGuide(),

          const SizedBox(height: 16),

          // 4. Open app settings
          OutlinedButton.icon(
            onPressed: _openAppSettings,
            icon: const Icon(LucideIcons.settings, size: 16),
            label: const Padding(
              padding: EdgeInsets.symmetric(vertical: 10),
              child: Text('Открыть настройки приложения'),
            ),
          ),

          const SizedBox(height: 24),

          // 5. Test push
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: MX.surfaceOverlay,
              borderRadius: BorderRadius.circular(MX.rLg),
              border: Border.all(color: MX.line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(LucideIcons.bell,
                        color: MX.accentAi, size: 18),
                    const SizedBox(width: 10),
                    Text('Тестовое уведомление',
                        style: t.textTheme.titleMedium),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Отправит push прямо сейчас. Если канал жив — придёт за 5–30 секунд.',
                  style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  height: 44,
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: MX.accentAi,
                      foregroundColor: Colors.black,
                    ),
                    onPressed: _testing ? null : _sendTestPush,
                    icon: _testing
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.black87),
                          )
                        : const Icon(LucideIcons.send, size: 16),
                    label: Text(_testing ? 'Отправляю…' : 'Отправить тест'),
                  ),
                ),
                if (_testResult != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _testResult!,
                    style: t.textTheme.bodySmall?.copyWith(color: MX.fg),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------

class _CheckTile extends StatelessWidget {
  const _CheckTile({
    required this.ok,
    required this.title,
    required this.subtitle,
    this.actionLabel,
    required this.onAction,
  });

  final bool ok;
  final String title;
  final String subtitle;
  final String? actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(
          color: ok ? MX.accentAi.withAlpha(60) : MX.accentSecurityLine,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: ok
                  ? MX.accentAi.withAlpha(40)
                  : MX.accentSecurity.withAlpha(40),
            ),
            child: Icon(
              ok ? LucideIcons.check : LucideIcons.x,
              size: 16,
              color: ok ? MX.accentAi : MX.accentSecurity,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: t.textTheme.bodyLarge
                        ?.copyWith(fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(subtitle,
                    style:
                        t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
              ],
            ),
          ),
          if (actionLabel != null) ...[
            const SizedBox(width: 8),
            TextButton(
              onPressed: onAction,
              child: Text(actionLabel!),
            ),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Vendor guides
// ---------------------------------------------------------------------------

class _GuideCard extends StatelessWidget {
  const _GuideCard({required this.title, required this.steps});
  final String title;
  final List<String> steps;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(top: 8, bottom: 4),
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: BoxDecoration(
        color: MX.accentAi.withAlpha(20),
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.accentAi.withAlpha(50)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(LucideIcons.smartphone,
                  size: 16, color: MX.accentAi),
              const SizedBox(width: 8),
              Text(title,
                  style: t.textTheme.titleSmall
                      ?.copyWith(color: MX.accentAi, letterSpacing: 0.3)),
            ],
          ),
          const SizedBox(height: 10),
          for (int i = 0; i < steps.length; i++) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 22,
                  child: Text(
                    '${i + 1}.',
                    style: t.textTheme.bodyMedium
                        ?.copyWith(color: MX.fgMuted),
                  ),
                ),
                Expanded(
                  child: Text(
                    steps[i],
                    style: t.textTheme.bodyMedium
                        ?.copyWith(color: MX.fg, height: 1.4),
                  ),
                ),
              ],
            ),
            if (i < steps.length - 1) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _XiaomiGuide extends StatelessWidget {
  const _XiaomiGuide();
  @override
  Widget build(BuildContext context) {
    return const _GuideCard(
      title: 'Xiaomi / HyperOS / MIUI',
      steps: [
        'Настройки → Приложения → Управление → Methodex → Автозапуск: ВКЛ.',
        'Там же → Расход батареи → выбрать «Без ограничений».',
        'Открой меню недавних → потяни Methodex вниз и нажми замочек, чтобы закрепить.',
        'Если включён режим энергосбережения — добавь Methodex в исключения.',
      ],
    );
  }
}

class _SamsungGuide extends StatelessWidget {
  const _SamsungGuide();
  @override
  Widget build(BuildContext context) {
    return const _GuideCard(
      title: 'Samsung / One UI',
      steps: [
        'Настройки → Обслуживание устройства → Батарея → Без ограничений → добавить Methodex.',
        'Настройки → Приложения → Methodex → Батарея → Без ограничений.',
        'Если активен «Режим энергосбережения» — выключи или добавь приложение в исключения.',
      ],
    );
  }
}

class _HuaweiGuide extends StatelessWidget {
  const _HuaweiGuide();
  @override
  Widget build(BuildContext context) {
    return const _GuideCard(
      title: 'Huawei / Honor / EMUI',
      steps: [
        'Настройки → Приложения → Methodex → Батарея → Запуск приложения: переключи на «Управлять вручную» и включи все три тумблера.',
        'Заблокируй приложение в недавних (потяни вниз → замочек).',
        'Отключи «Энергосбережение» или добавь Methodex в исключения.',
      ],
    );
  }
}

class _OppoVivoGuide extends StatelessWidget {
  const _OppoVivoGuide();
  @override
  Widget build(BuildContext context) {
    return const _GuideCard(
      title: 'OPPO / Realme / Vivo',
      steps: [
        'Настройки → Батарея → Управление расходом → Methodex → разрешить фоновую работу.',
        'Настройки → Приложения → Methodex → Уведомления — включить все категории.',
        'Заблокируй приложение в недавних задачах.',
      ],
    );
  }
}
