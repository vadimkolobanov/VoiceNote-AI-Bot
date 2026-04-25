import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// S11 — Голосовой захват (PRODUCT_PLAN.md §2.7).
///
/// Минимальный M4-stub: пульсирующий микрофон + кнопки «Стоп»/«Отмена».
/// Реальная запись (`record` package), STT и сохранение момента — в M5.
class VoiceCaptureScreen extends StatefulWidget {
  const VoiceCaptureScreen({super.key});

  @override
  State<VoiceCaptureScreen> createState() => _VoiceCaptureScreenState();
}

class _VoiceCaptureScreenState extends State<VoiceCaptureScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  @override
  void initState() {
    super.initState();
    HapticFeedback.mediumImpact();
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: MX.bgBase,
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.topRight,
              child: IconButton(
                icon: const Icon(Icons.close, color: MX.fgMuted, size: 28),
                onPressed: () => context.pop(),
              ),
            ),
            Expanded(
              child: Center(
                child: AnimatedBuilder(
                  animation: _pulse,
                  builder: (context, child) {
                    final scale = 1 + (_pulse.value * 0.12);
                    return Transform.scale(scale: scale, child: child);
                  },
                  child: Container(
                    width: 160,
                    height: 160,
                    decoration: BoxDecoration(
                      gradient: MX.brandGradient,
                      shape: BoxShape.circle,
                      boxShadow: MX.fabGlow,
                    ),
                    child: const Icon(Icons.mic, size: 72, color: Colors.white),
                  ),
                ),
              ),
            ),
            Text('Слушаю…', style: t.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Скажи что-нибудь — я запомню.',
              style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
            ),
            const SizedBox(height: 32),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  TextButton(
                    onPressed: () => context.pop(),
                    child: const Text('Отмена'),
                  ),
                  FilledButton(
                    onPressed: () {
                      // M5: сохранить момент и выйти
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Запись пока не сохраняется. Реализация в M5.')),
                      );
                      context.pop();
                    },
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                      child: Text('Стоп'),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}
