import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/billing/data/billing_repository.dart';
import 'package:voicenote_ai/features/billing/presentation/payment_webview_screen.dart';

/// S12 — Paywall (PRODUCT_PLAN.md §8). Дёргает /billing/subscribe и
/// открывает PaymentWebViewScreen с confirmation_url или mock-flow.
class PaywallScreen extends ConsumerStatefulWidget {
  const PaywallScreen({super.key});

  @override
  ConsumerState<PaywallScreen> createState() => _PaywallScreenState();
}

class _PaywallScreenState extends ConsumerState<PaywallScreen> {
  bool _busy = false;
  String? _busyPlan;

  Future<void> _subscribe(String planCode) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _busyPlan = planCode;
    });
    try {
      final result =
          await ref.read(billingRepositoryProvider).subscribe(planCode);
      if (!mounted) return;
      if (result.confirmationUrl == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Платёжный URL не получен.')),
        );
        return;
      }
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PaymentWebViewScreen(
            confirmationUrl: result.confirmationUrl!,
            externalId: result.externalId,
            isMock: result.isMock,
          ),
        ),
      );
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
          _busyPlan = null;
        });
      }
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final plansAsync = ref.watch(billingPlansProvider);

    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        surfaceTintColor: Colors.transparent,
        title: const Text('Pro'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [MX.accentAi, MX.accentPurple],
              ),
              borderRadius: BorderRadius.circular(MX.rLg),
              boxShadow: MX.fabGlow,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Pro',
                    style: t.textTheme.displaySmall?.copyWith(color: Colors.white)),
                const SizedBox(height: 8),
                Text(
                  'Я начинаю помнить тебя — а не просто записывать.',
                  style: t.textTheme.bodyLarge?.copyWith(color: Colors.white),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const _Bullet(text: 'Память глубже 30 дней'),
          const _Bullet(text: 'Вопросы к ИИ по твоим записям'),
          const _Bullet(text: '«Что я о тебе знаю» — портрет из фактов'),
          const _Bullet(text: 'Проактивные подсказки'),
          const _Bullet(text: 'Расширенные лимиты голоса'),
          const SizedBox(height: 28),

          ...plansAsync.when(
            loading: () => [
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(20),
                  child: CircularProgressIndicator(color: MX.accentAi),
                ),
              ),
            ],
            error: (e, _) => [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: MX.accentSecuritySoft,
                  borderRadius: BorderRadius.circular(MX.rMd),
                  border: Border.all(color: MX.accentSecurityLine),
                ),
                child: Text('Не удалось получить тарифы: $e',
                    style: t.textTheme.bodySmall),
              ),
            ],
            data: (plans) {
              return [
                for (var i = 0; i < plans.length; i++) ...[
                  _PlanCard(
                    plan: plans[i],
                    highlight: plans[i].code == 'pro_yearly',
                    busy: _busy && _busyPlan == plans[i].code,
                    onTap: () => _subscribe(plans[i].code),
                  ),
                  if (i < plans.length - 1) const SizedBox(height: 12),
                ],
              ];
            },
          ),
          const SizedBox(height: 16),
          Center(
            child: Text(
              'Можно отменить в любой момент. Авто-продление каждый период.',
              style: t.textTheme.bodySmall?.copyWith(color: MX.fgFaint),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: MX.accentAiSoft,
              borderRadius: BorderRadius.circular(MX.rXs),
            ),
            child: const Icon(Icons.check, color: MX.accentAi, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
          ),
        ],
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.plan,
    required this.highlight,
    required this.busy,
    required this.onTap,
  });

  final BillingPlan plan;
  final bool highlight;
  final bool busy;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final borderColor = highlight ? MX.accentAi : MX.lineStrong;
    final period = plan.code == 'pro_monthly'
        ? 'в месяц'
        : 'в год · ~${(double.parse(plan.priceRub) / 12).toStringAsFixed(0)} ₽/мес';

    return Material(
      color: highlight ? MX.accentAiSoft : MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rLg),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rLg),
        onTap: busy ? null : onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rLg),
            border: Border.all(color: borderColor, width: highlight ? 1.5 : 1),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(plan.title, style: t.textTheme.titleMedium),
                        if (highlight) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: MX.accentAi,
                              borderRadius: BorderRadius.circular(MX.rFull),
                            ),
                            child: const Text(
                              'выгоднее ~27%',
                              style: TextStyle(
                                  color: MX.bgBase,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(period,
                        style:
                            t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                  ],
                ),
              ),
              if (busy)
                const SizedBox(
                  width: 22, height: 22,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: MX.accentAi),
                )
              else
                Text('${plan.priceRub} ₽',
                    style: t.textTheme.titleLarge
                        ?.copyWith(fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}
