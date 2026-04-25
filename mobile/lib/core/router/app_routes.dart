/// Маршруты приложения (PRODUCT_PLAN.md §7.4).
abstract final class AppRoutes {
  static const splash = '/';
  static const login = '/login';

  // 4 нижних таба
  static const today = '/today';
  static const timeline = '/timeline';
  static const rhythm = '/rhythm';
  static const profile = '/profile';

  // Модал-диалоги, доступные с любого таба
  static const voiceCapture = '/capture';

  // Прочие push-экраны (детали, paywall и т. д.) появятся в M5/M6
}
