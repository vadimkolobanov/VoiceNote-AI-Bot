import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/profile/data/repositories/profile_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

class AchievementsScreen extends ConsumerWidget {
  const AchievementsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(achievementsProvider);
    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: MxAppBar(
        title: 'Достижения',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 22),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) =>
            AppErrorView(error: e, onRetry: () => ref.invalidate(achievementsProvider)),
        data: (items) {
          if (items.isEmpty) {
            return const EmptyStateView(
              icon: Icons.emoji_events_outlined,
              title: 'Пока нет достижений',
            );
          }
          return GridView.builder(
            padding: const EdgeInsets.all(16),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 0.85,
            ),
            itemCount: items.length,
            itemBuilder: (_, i) {
              final a = items[i];
              final scheme = Theme.of(context).colorScheme;
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Opacity(
                        opacity: a.earned ? 1 : 0.3,
                        child: Text(a.icon, style: const TextStyle(fontSize: 36)),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        a.name,
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.labelMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                              color: a.earned ? scheme.onSurface : scheme.onSurfaceVariant,
                            ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '+${a.xpReward} XP',
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: a.earned ? scheme.primary : scheme.outline,
                            ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
