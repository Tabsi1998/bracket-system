import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { CircleHelp } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const FALLBACK_FAQ_ITEMS = [
  {
    id: "faq-public-overview",
    question: "Wie nutze ich das System als neuer Benutzer?",
    answer:
      "1) Registrieren/Einloggen\n2) Team erstellen oder Team beitreten\n3) Turnier öffnen und registrieren\n4) Im Match-Hub Termin, Setup und Ergebnis verwalten.\n\nTipp: Schau dir zuerst die Turnier-Regeln an!",
  },
  {
    id: "faq-public-team-vs-solo",
    question: "Wann spiele ich als Team und wann Solo?",
    answer:
      "Bei Team-Turnieren meldest du ein passendes Sub-Team an. Bei Solo-Turnieren spielst du direkt als Benutzer ohne Team-Auswahl.\n\nSub-Teams werden vom Hauptteam erstellt und können für verschiedene Turniere genutzt werden.",
  },
  {
    id: "faq-public-matchday",
    question: "Wie funktionieren Liga-Spieltage / Wochen?",
    answer:
      "In Liga- oder Round-Robin-Formaten gibt es pro Spieltag feste Wochenfenster. Das konkrete Match-Datum/Uhrzeit stimmen die Teams im Match-Hub ab.\n\n⏰ Terminabstimmung:\n• Ein Team schlägt einen Termin vor\n• Das andere Team bestätigt oder macht Gegenvorschlag\n• Bei keiner Einigung gilt der Standard-Termin (z.B. Mittwoch 19:00)",
  },
  {
    id: "faq-public-payment",
    question: "Was passiert bei Problemen mit Zahlung oder Check-in?",
    answer:
      "Bei kostenpflichtigen Turnieren ist Check-in nur nach erfolgreicher Zahlung möglich. Fehlgeschlagene Zahlungen können über den Retry-Flow erneut gestartet werden.\n\nZahlungsmethoden:\n• Stripe (Kreditkarte)\n• PayPal (falls aktiviert)",
  },
  {
    id: "faq-scheduling",
    question: "Wie läuft die Termin-Abstimmung ab?",
    answer:
      "1. Gehe zum Match-Hub deines Matches\n2. Schlage einen Termin vor (Datum + Uhrzeit)\n3. Dein Gegner sieht den Vorschlag und kann:\n   • Den Termin bestätigen\n   • Einen Gegenvorschlag machen\n4. Sobald ein Team einen Vorschlag akzeptiert, ist der Termin fest\n\n⚠️ Falls keine Einigung: Der Standard-Termin wird automatisch gesetzt!",
  },
  {
    id: "faq-subteams",
    question: "Was sind Sub-Teams und wofür brauche ich sie?",
    answer:
      "Sub-Teams sind Unterteams deines Hauptteams. Vorteile:\n\n• Verschiedene Rosters für verschiedene Turniere\n• Erben automatisch Profil-Infos vom Hauptteam\n• Ermöglichen flexible Team-Aufstellungen\n\nSo erstellst du ein Sub-Team:\n1. Gehe zu 'Meine Teams'\n2. Klicke bei deinem Hauptteam auf 'Sub-Team'\n3. Gib Name und Tag ein",
  },
  {
    id: "faq-checkin",
    question: "Was bedeutet Check-in und wie funktioniert es?",
    answer:
      "Der Check-in ist die Bestätigung, dass dein Team am Turnier teilnimmt.\n\n⏰ Ablauf:\n1. Check-in-Phase startet (meist 30 Min. vor Turnierbeginn)\n2. Gehe zur Turnier-Seite und klicke 'Check-in'\n3. Nach Ende der Phase werden nur eingecheckte Teams in den Bracket aufgenommen\n\n⚠️ Ohne Check-in = Keine Teilnahme!",
  },
  {
    id: "faq-bracket-types",
    question: "Welche Turnier-Formate gibt es?",
    answer:
      "Unterstützte Formate:\n\n🏆 Single Elimination - Eine Niederlage = Raus\n🏆 Double Elimination - 2 Niederlagen = Raus (Winner/Loser Bracket)\n📊 Liga / Round Robin - Jeder gegen jeden\n📊 Gruppenphase + Playoffs - Erst Gruppen, dann KO\n🔄 Swiss System - Ähnlich starke Teams spielen gegeneinander\n👑 King of the Hill - Verteidiger vs. Herausforderer",
  },
  {
    id: "faq-score-submission",
    question: "Wie melde ich ein Match-Ergebnis?",
    answer:
      "1. Öffne den Match-Hub nach dem Spiel\n2. Klicke 'Ergebnis eintragen'\n3. Gib den Score ein\n4. Das andere Team bestätigt das Ergebnis\n\n✅ Bei Übereinstimmung: Automatische Bestätigung\n❌ Bei Widerspruch: Admin entscheidet\n\nBeweis-Screenshots können hochgeladen werden.",
  },
  {
    id: "faq-notifications",
    question: "Wie erhalte ich Benachrichtigungen?",
    answer:
      "Das System benachrichtigt dich automatisch über:\n\n• Neue Matches und Spieltermine\n• Check-in Erinnerungen\n• Ergebnis-Bestätigungen\n• Termin-Erinnerungen (24h vor Ablauf)\n• Team-Einladungen\n\nBenachrichtigungen siehst du im Glocken-Symbol oben rechts.",
  },
];

export default function FAQPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    axios.get(`${API}/faq`)
      .then((res) => {
        if (!active) return;
        const faqItems = Array.isArray(res.data?.items) ? res.data.items : [];
        setItems(faqItems.length ? faqItems : FALLBACK_FAQ_ITEMS);
      })
      .catch(() => {
        if (!active) return;
        setItems(FALLBACK_FAQ_ITEMS);
        toast.warning("FAQ-API nicht erreichbar. Fallback-Inhalte werden angezeigt.");
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => { active = false; };
  }, []);

  return (
    <div data-testid="faq-page" className="pt-20 min-h-screen">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center gap-3 mb-6">
          <CircleHelp className="w-8 h-8 text-yellow-500" />
          <div>
            <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight">
              FAQ
            </h1>
            <p className="text-zinc-400 text-sm mt-1">
              Antworten und Leitfaden zur Nutzung des kompletten Systems.
            </p>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="glass rounded-xl border border-white/5 p-5 sm:p-6"
        >
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : items.length === 0 ? (
            <p className="text-zinc-500 text-sm text-center py-8">Noch keine FAQ-Einträge vorhanden.</p>
          ) : (
            <Accordion type="single" collapsible className="w-full">
              {items.map((item, idx) => (
                <AccordionItem
                  key={item.id || `faq-item-${idx}`}
                  value={item.id || `faq-item-${idx}`}
                  className="border-white/10"
                >
                  <AccordionTrigger className="text-base text-white hover:no-underline py-4">
                    <span className="text-left">{item.question}</span>
                  </AccordionTrigger>
                  <AccordionContent className="text-zinc-400 text-sm leading-relaxed whitespace-pre-line">
                    {item.answer}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </motion.div>
      </div>
    </div>
  );
}
