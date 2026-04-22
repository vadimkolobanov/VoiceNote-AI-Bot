import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/data/models/dev_user.dart';
import 'package:voicenote_ai/features/auth/data/repositories/auth_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

final _devUsersProvider = FutureProvider.autoDispose<List<DevUser>>((ref) async {
  return ref.watch(authRepositoryProvider).listDevUsers();
});

/// Dev-экран входа: показывает список существующих Telegram-пользователей,
/// у каждого видно число заметок. Тап — входим под этим пользователем.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  int? _loggingInId;

  Future<void> _login(int telegramId) async {
    setState(() => _loggingInId = telegramId);
    try {
      await ref.read(sessionControllerProvider.notifier).devLogin(telegramId);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Не удалось войти')),
        );
      }
    } finally {
      if (mounted) setState(() => _loggingInId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final async = ref.watch(_devUsersProvider);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 32, 24, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: scheme.primary,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: const Icon(Icons.graphic_eq, size: 36, color: Colors.white),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'VoiceNote AI',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Выберите пользователя, чтобы увидеть его заметки',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () async => ref.invalidate(_devUsersProvider),
                child: async.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => AppErrorView(
                    error: e,
                    onRetry: () => ref.invalidate(_devUsersProvider),
                  ),
                  data: (users) {
                    if (users.isEmpty) {
                      return const EmptyStateView(
                        icon: Icons.person_off_outlined,
                        title: 'В базе нет пользователей',
                        subtitle: 'Зайдите в Telegram-бот и создайте заметку',
                      );
                    }
                    return ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                      itemCount: users.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) {
                        final u = users[i];
                        final isLoading = _loggingInId == u.telegramId;
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: scheme.primaryContainer,
                              child: Text(
                                _avatarLetter(u),
                                style: TextStyle(
                                  color: scheme.onPrimaryContainer,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            title: Text(
                              u.displayName,
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            subtitle: Text(
                              'id ${u.telegramId} · ${u.notesCount} заметок',
                            ),
                            trailing: isLoading
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.chevron_right),
                            onTap: _loggingInId == null ? () => _login(u.telegramId) : null,
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _avatarLetter(DevUser u) {
    final name = u.displayName.trim();
    if (name.isEmpty) return '?';
    final first = name[0];
    return first == '@' && name.length > 1
        ? name[1].toUpperCase()
        : first.toUpperCase();
  }
}
