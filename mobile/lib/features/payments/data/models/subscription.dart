enum SubscriptionPlan { monthly, yearly }

extension SubscriptionPlanX on SubscriptionPlan {
  String get apiValue => switch (this) {
        SubscriptionPlan.monthly => 'monthly',
        SubscriptionPlan.yearly => 'yearly',
      };

  String get russianLabel => switch (this) {
        SubscriptionPlan.monthly => 'Месяц',
        SubscriptionPlan.yearly => 'Год',
      };
}

class Subscription {
  const Subscription({
    required this.status,
    required this.plan,
    required this.autoRenew,
    this.expiresAt,
    this.startedAt,
  });

  final String status; // active | cancelled | expired | pending
  final SubscriptionPlan? plan;
  final DateTime? expiresAt;
  final DateTime? startedAt;
  final bool autoRenew;

  bool get isActive => status == 'active';

  factory Subscription.fromJson(Map<String, dynamic> json) {
    SubscriptionPlan? plan;
    switch (json['plan'] as String?) {
      case 'monthly':
        plan = SubscriptionPlan.monthly;
      case 'yearly':
        plan = SubscriptionPlan.yearly;
    }
    return Subscription(
      status: (json['status'] as String?) ?? 'inactive',
      plan: plan,
      expiresAt: json['expires_at'] != null
          ? DateTime.parse(json['expires_at'] as String)
          : null,
      startedAt: json['started_at'] != null
          ? DateTime.parse(json['started_at'] as String)
          : null,
      autoRenew: (json['auto_renew'] as bool?) ?? false,
    );
  }
}
