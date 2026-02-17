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
      "1) Registrieren/Einloggen  2) Team erstellen oder Team beitreten  3) Turnier öffnen und registrieren  4) Im Match-Hub Termin, Setup und Ergebnis verwalten.",
  },
  {
    id: "faq-public-team-vs-solo",
    question: "Wann spiele ich als Team und wann Solo?",
    answer:
      "Bei Team-Turnieren meldest du ein passendes Sub-Team an. Bei Solo-Turnieren spielst du direkt als Benutzer ohne Team-Auswahl.",
  },
  {
    id: "faq-public-matchday",
    question: "Wie funktionieren Liga-Spieltage / Wochen?",
    answer:
      "In Liga- oder Round-Robin-Formaten gibt es pro Spieltag feste Wochenfenster. Das konkrete Match-Datum/Uhrzeit stimmen die Teams im Match-Hub ab.",
  },
  {
    id: "faq-public-payment",
    question: "Was passiert bei Problemen mit Zahlung oder Check-in?",
    answer:
      "Bei kostenpflichtigen Turnieren ist Check-in nur nach erfolgreicher Zahlung möglich. Fehlgeschlagene Zahlungen können über den Retry-Flow erneut gestartet werden.",
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
