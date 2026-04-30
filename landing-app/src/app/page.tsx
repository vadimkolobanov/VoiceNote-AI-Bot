import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import Hero from '@/components/secretary/Hero';
import Features from '@/components/secretary/Features';
import AppPreview from '@/components/secretary/AppPreview';
import Pricing from '@/components/secretary/Pricing';
import FAQ from '@/components/secretary/FAQ';
import CTA from '@/components/secretary/CTA';

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Features />
        <AppPreview />
        <Pricing />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
