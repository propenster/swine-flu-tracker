import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { GoogleAnalytics } from "@next/third-parties/google";
import Script from "next/dist/client/script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://swine-flu-tracker.pages.dev"),  title: {
    default: "US Swine Influenza HA Tracker",
    template: "%s | US Swine Influenza HA Tracker",
  },
  description:
    "An automated, end-to-end surveillance pipeline for U.S. swine influenza A virus (IAV) hemagglutinin (HA) sequences. Interactive phylogenetics and clade visualization.",
  keywords: [
    "swine influenza",
    "influenza A virus",
    "IAV",
    "hemagglutinin",
    "HA",
    "swine flu",
    "US swine",
    "surveillance",
    "phylogenetics",
    "bioinformatics",
    "genomic epidemiology",
    "clade classification",
    "octoFLU",
    "Nextstrain",
    "Auspice",
  ],
  authors: [{ name: "Faith Olusegun", url: "https://github.com/propenster" }],
  creator: "Faith Olusegun",
  publisher: "Faith Olusegun",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://swine-flu-tracker.pages.dev",
    siteName: "US Swine Influenza HA Tracker",
    title: "US Swine Influenza HA Tracker",
    description:
      "Interactive dashboard for tracking swine influenza A virus clades across U.S. states.",
    images: [
      {
        url: "/og-image.png", // Add a 1200x630 image to your /public folder
        width: 1200,
        height: 630,
        alt: "US Swine Influenza HA Tracker Dashboard",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "US Swine Influenza HA Tracker",
    description:
      "Interactive dashboard for tracking swine influenza A virus clades across U.S. states.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: "/",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=G-9VFDHH991S`}
        strategy="afterInteractive"
      />
      <Script id="google-analytics" strategy="afterInteractive">
        {`
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-9VFDHH991S');
  `}
      </Script>
      <body className="min-h-full flex flex-col">{children}</body>
      {/* <GoogleAnalytics gaId="G-9VFDHH991S" /> */}
    </html>
  );
}
