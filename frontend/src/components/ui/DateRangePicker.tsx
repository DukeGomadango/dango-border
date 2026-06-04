"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from "lucide-react";

interface DateRange {
  from: string;
  to: string;
}

interface DateRangePickerProps {
  dateRange: DateRange;
  onDateRangeChange: (range: DateRange) => void;
}

export function DateRangePicker({ dateRange, onDateRangeChange }: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calendar navigation state
  const today = useMemo(() => new Date(), []);
  const [currentDate, setCurrentDate] = useState(() => {
    if (dateRange.from) {
      return new Date(dateRange.from);
    }
    return new Date();
  });

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth(); // 0-indexed

  // Close calendar when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Sync calendar display month when dateRange changes externally (React 19 recommended state adjustment pattern)
  const [prevFrom, setPrevFrom] = useState(dateRange.from);
  if (dateRange.from !== prevFrom) {
    setPrevFrom(dateRange.from);
    if (dateRange.from) {
      setCurrentDate(new Date(dateRange.from));
    }
  }

  // Helper: get standard YYYY-MM-DD local string
  const toLocalDateString = (date: Date): string => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };

  // Preset Date range generators
  const presets = useMemo(() => {
    // Today
    const todayStr = toLocalDateString(today);
    const todayPlus6 = new Date(today);
    todayPlus6.setDate(today.getDate() + 6);
    const todayPlus6Str = toLocalDateString(todayPlus6);
    
    // Tomorrow
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    const tomorrowStr = toLocalDateString(tomorrow);
    const tomorrowPlus6 = new Date(tomorrow);
    tomorrowPlus6.setDate(tomorrow.getDate() + 6);
    const tomorrowPlus6Str = toLocalDateString(tomorrowPlus6);

    // Event Date Range (Starts next Tuesday, ends the following Monday)
    const nextTue = new Date(today);
    nextTue.setDate(today.getDate() + ((1 + 7 - today.getDay()) % 7 || 7));
    const nextMon = new Date(nextTue);
    nextMon.setDate(nextTue.getDate() + 6);

    return [
      {
        label: "今日",
        range: { from: todayStr, to: todayPlus6Str },
      },
      {
        label: "明日",
        range: { from: tomorrowStr, to: tomorrowPlus6Str },
      },
      {
        label: "イベント全体",
        range: {
          from: toLocalDateString(nextTue),
          to: toLocalDateString(nextMon),
        },
      },
    ];
  }, [today]);

  // Generate calendar days
  const calendarDays = useMemo(() => {
    // First day of the month
    const firstDayOfMonth = new Date(year, month, 1);
    // Day of the week of first day (0 = Sun, 1 = Mon, ..., 6 = Sat)
    const startDayOfWeek = firstDayOfMonth.getDay();
    
    // Total days in current month
    const totalDays = new Date(year, month + 1, 0).getDate();
    
    // Previous month total days (for padding)
    const prevMonthTotalDays = new Date(year, month, 0).getDate();

    const days = [];

    // Padding from previous month
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, prevMonthTotalDays - i);
      days.push({ date: d, isCurrentMonth: false });
    }

    // Current month days
    for (let i = 1; i <= totalDays; i++) {
      const d = new Date(year, month, i);
      days.push({ date: d, isCurrentMonth: true });
    }

    // Padding for next month to complete the grid (usually 42 cells)
    const totalCells = 42; // 6 rows * 7 days
    const nextMonthDaysToAdd = totalCells - days.length;
    for (let i = 1; i <= nextMonthDaysToAdd; i++) {
      const d = new Date(year, month + 1, i);
      days.push({ date: d, isCurrentMonth: false });
    }

    return days;
  }, [year, month]);

  const handlePrevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const handleDaySelect = (date: Date) => {
    const clickedStr = toLocalDateString(date);
    
    // Case 1: No range selected, or range already complete (start and end selected)
    // We start a new range selection
    if (!dateRange.from || (dateRange.from && dateRange.to)) {
      onDateRangeChange({ from: clickedStr, to: "" });
    } 
    // Case 2: Start selected, selecting end date
    else {
      const fromTime = new Date(dateRange.from).getTime();
      const clickedTime = date.getTime();

      if (clickedTime < fromTime) {
        // If clicked date is before start date, make it the new start date
        onDateRangeChange({ from: clickedStr, to: "" });
      } else {
        // Set end date and close dropdown
        onDateRangeChange({ from: dateRange.from, to: clickedStr });
        setIsOpen(false);
      }
    }
  };

  // Check state of a specific day
  const getDayState = (date: Date) => {
    const dateStr = toLocalDateString(date);
    const fromVal = dateRange.from;
    const toVal = dateRange.to;

    const isStart = fromVal === dateStr;
    const isEnd = toVal === dateStr;
    const isSelected = isStart || isEnd;
    
    let isInRange = false;
    if (fromVal && toVal && dateStr > fromVal && dateStr < toVal) {
      isInRange = true;
    }

    return { isSelected, isStart, isInRange };
  };

  // Determine active preset (if any)
  const activePreset = useMemo(() => {
    return presets.find(
      (p) => p.range.from === dateRange.from && p.range.to === dateRange.to
    );
  }, [dateRange, presets]);

  // Display label on the main input button
  const displayLabel = useMemo(() => {
    if (!dateRange.from) return "日付範囲を選択してください";
    if (dateRange.from && !dateRange.to) {
      return `${dateRange.from.slice(5)} 〜 終了日を選択...`;
    }
    if (dateRange.from === dateRange.to) {
      return `${dateRange.from}`;
    }
    return `${dateRange.from} 〜 ${dateRange.to}`;
  }, [dateRange]);

  const monthNames = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
  const weekDays = ["日", "月", "火", "水", "木", "金", "土"];

  return (
    <div className="relative inline-block w-full md:w-auto" ref={containerRef}>
      <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block mb-1">
        表示期間
      </label>
      
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full md:w-64 bg-slate-950/60 border border-white/10 hover:border-purple-500/50 rounded-xl px-4 py-2.5 text-sm text-white font-bold outline-none flex items-center justify-between transition-all shadow-md backdrop-blur-md cursor-pointer"
        type="button"
      >
        <span className="flex items-center gap-2 truncate">
          <CalendarIcon className="w-4 h-4 text-purple-400 shrink-0" />
          {displayLabel}
        </span>
        {activePreset && (
          <span className="text-[10px] bg-purple-500/20 text-purple-300 font-extrabold px-1.5 py-0.5 rounded uppercase">
            {activePreset.label}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 z-50 glass-card rounded-2xl p-4 w-[340px] flex flex-col gap-4 border border-white/10 shadow-2xl animate-in fade-in duration-200">
          {/* Quick presets */}
          <div className="flex gap-2 border-b border-white/5 pb-3">
            {presets.map((preset) => {
              const isSelected =
                dateRange.from === preset.range.from && dateRange.to === preset.range.to;
              return (
                <button
                  key={preset.label}
                  onClick={() => {
                    onDateRangeChange(preset.range);
                    setIsOpen(false);
                  }}
                  className={`flex-1 text-center py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                    isSelected
                      ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-600/10"
                      : "bg-white/5 text-slate-400 hover:text-white hover:bg-white/10"
                  }`}
                  type="button"
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          {/* Month selector header */}
          <div className="flex items-center justify-between px-1">
            <button
              onClick={handlePrevMonth}
              className="p-1 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-colors cursor-pointer"
              type="button"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm font-extrabold text-white">
              {year}年 {monthNames[month]}
            </span>
            <button
              onClick={handleNextMonth}
              className="p-1 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-colors cursor-pointer"
              type="button"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {/* Grid calendar */}
          <div className="flex flex-col gap-1">
            {/* Week days header */}
            <div className="grid grid-cols-7 text-center">
              {weekDays.map((day) => (
                <span
                  key={day}
                  className="text-[10px] font-extrabold text-slate-500 uppercase tracking-wider py-1"
                >
                  {day}
                </span>
              ))}
            </div>

            {/* Days grid */}
            <div className="grid grid-cols-7 gap-y-1 text-center">
              {calendarDays.map(({ date, isCurrentMonth }, idx) => {
                const { isSelected, isStart, isInRange } = getDayState(date);
                const isToday = toLocalDateString(date) === toLocalDateString(today);

                return (
                  <button
                    key={idx}
                    onClick={() => handleDaySelect(date)}
                    className={`h-8 w-8 mx-auto flex items-center justify-center text-xs font-bold rounded-lg transition-all relative cursor-pointer
                      ${!isCurrentMonth ? "text-slate-600 opacity-40 hover:text-slate-400" : "text-slate-300 hover:bg-white/5"}
                      ${isToday && !isSelected ? "ring-1 ring-purple-500/50 text-purple-300" : ""}
                      ${isInRange ? "bg-purple-600/20 text-purple-200 rounded-none first:rounded-l-lg last:rounded-r-lg" : ""}
                      ${
                        isSelected
                          ? "bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-black shadow-lg shadow-purple-500/20 z-10"
                          : ""
                      }
                    `}
                    type="button"
                  >
                    {date.getDate()}
                    {isStart && dateRange.to && (
                      <span className="absolute bottom-0.5 w-1 h-1 rounded-full bg-white/70" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
