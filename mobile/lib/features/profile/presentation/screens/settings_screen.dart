import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/profile/data/repositories/profile_repository.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final _city = TextEditingController();
  late final _timezone = TextEditingController();
  bool _digestEnabled = true;
  TimeOfDay _digestTime = const TimeOfDay(hour: 8, minute: 30);
  bool _saving = false;
  bool _initialized = false;

  @override
  void dispose() {
    _city.dispose();
    _timezone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(profileRepositoryProvider).updateProfile(
            cityName: _city.text.trim().isEmpty ? null : _city.text.trim(),
            timezone: _timezone.text.trim().isEmpty ? null : _timezone.text.trim(),
            dailyDigestEnabled: _digestEnabled,
            dailyDigestTime:
                '${_digestTime.hour.toString().padLeft(2, '0')}:${_digestTime.minute.toString().padLeft(2, '0')}',
          );
      await ref.read(sessionControllerProvider.notifier).refreshUser();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Сохранено')),
      );
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(sessionControllerProvider).user;
    if (user != null && !_initialized) {
      _city.text = user.cityName ?? '';
      _timezone.text = user.timezone;
      _initialized = true;
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Настройки'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Сохранить'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _SectionTitle('Утренний дайджест'),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _digestEnabled,
            onChanged: (v) => setState(() => _digestEnabled = v),
            title: const Text('Получать утренний дайджест'),
            subtitle: const Text('Погода, задачи и напоминания на день'),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Время дайджеста'),
            trailing: OutlinedButton(
              onPressed: _digestEnabled
                  ? () async {
                      final picked = await showTimePicker(
                        context: context,
                        initialTime: _digestTime,
                      );
                      if (picked != null) setState(() => _digestTime = picked);
                    }
                  : null,
              child: Text(_digestTime.format(context)),
            ),
          ),
          const SizedBox(height: 12),
          _SectionTitle('Локация'),
          TextField(
            controller: _city,
            decoration: const InputDecoration(
              labelText: 'Город',
              hintText: 'Например, Москва',
              prefixIcon: Icon(Icons.location_city_outlined),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _timezone,
            decoration: const InputDecoration(
              labelText: 'Часовой пояс',
              hintText: 'Europe/Moscow',
              prefixIcon: Icon(Icons.schedule),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);
  final String title;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(
          title.toUpperCase(),
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                fontWeight: FontWeight.w700,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      );
}
